"""Heuristic JPQL and Spring Data method-name translator."""

from __future__ import annotations

import re


class JPQLTranslator:
    """Translates common JPQL and repository method shapes to SQLAlchemy snippets."""

    METHOD_PREFIXES = ("findBy", "existsBy", "countBy", "deleteBy", "findAllBy")

    def translate_jpql(self, jpql: str, entity: str, session_var: str = "self.db") -> str | None:
        text = jpql.strip()
        if text.startswith("@Query"):
            text = text[text.find("(") + 1:text.rfind(")")]
        text = text.strip().strip('"').strip("'")
        normalized = re.sub(r"\s+", " ", text)
        entity = entity.removesuffix("Entity")

        delete_match = re.search(rf"DELETE\s+FROM\s+{entity}\s+\w+\s+WHERE\s+(.+)$", normalized, re.IGNORECASE)
        if delete_match:
            where_expr = self._translate_where(delete_match.group(1), entity)
            return (
                f"await {session_var}.execute(delete({entity}).where({where_expr}))\n"
                f"await {session_var}.commit()"
            )

        count_match = re.search(rf"SELECT\s+COUNT\(\w+\)\s+FROM\s+{entity}\s+\w+(?:\s+WHERE\s+(.+))?$", normalized, re.IGNORECASE)
        if count_match:
            where_expr = self._translate_where(count_match.group(1) or "", entity)
            suffix = f".where({where_expr})" if where_expr else ""
            return (
                f"result = await {session_var}.execute(select(func.count()).select_from({entity}){suffix})\n"
                "return result.scalar_one()"
            )

        select_match = re.search(rf"SELECT\s+\w+\s+FROM\s+{entity}\s+\w+(?:\s+WHERE\s+(.+?))?(?:\s+ORDER\s+BY\s+(.+))?$", normalized, re.IGNORECASE)
        if select_match:
            where_expr = self._translate_where(select_match.group(1) or "", entity)
            order_expr = self._translate_order(select_match.group(2) or "", entity)
            query = f"select({entity})"
            if where_expr:
                query += f".where({where_expr})"
            if order_expr:
                query += f".order_by({order_expr})"
            return (
                f"result = await {session_var}.execute({query})\n"
                "return result.scalars().all()"
            )

        return None

    def translate_method_name(self, method_name: str, entity: str) -> str | None:
        if not method_name.startswith(self.METHOD_PREFIXES):
            return None

        if method_name == "findAll":
            return f"result = await self.db.execute(select({entity}))\nreturn result.scalars().all()"
        if method_name == "findById":
            return f"return await self.db.get({entity}, id)"

        prefix = next((item for item in self.METHOD_PREFIXES if method_name.startswith(item)), "")
        tail = method_name[len(prefix):]
        order_by = None
        if "OrderBy" in tail:
            tail, order_by = tail.split("OrderBy", 1)

        conditions = []
        for token in re.split(r"And", tail):
            if not token:
                continue
            operator = "=="
            column = token
            if token.endswith("Containing"):
                column = token[:-10]
                operator = "contains"
            elif token.endswith("Before"):
                column = token[:-6]
                operator = "<"
            elif token.endswith("After"):
                column = token[:-5]
                operator = ">"

            param_name = self._camel_to_snake(column)
            model_attr = f"{entity}.{param_name}"
            if operator == "contains":
                conditions.append(f"{model_attr}.contains({param_name})")
            else:
                conditions.append(f"{model_attr} {operator} {param_name}")

        where_clause = ", ".join(conditions)
        query = f"select({entity})"
        if prefix == "existsBy":
            query = f"select(exists().where({where_clause}))"
            return f"result = await self.db.execute({query})\nreturn bool(result.scalar())"
        if prefix == "countBy":
            query = f"select(func.count()).select_from({entity})"
            if where_clause:
                query += f".where({where_clause})"
            return f"result = await self.db.execute({query})\nreturn result.scalar_one()"
        if prefix == "deleteBy":
            return (
                f"await self.db.execute(delete({entity}).where({where_clause}))\n"
                "await self.db.commit()"
            )

        if where_clause:
            query += f".where({where_clause})"
        if order_by:
            query += f".order_by({self._translate_order(order_by, entity)})"

        if prefix == "findBy" and len(conditions) == 1 and not order_by:
            return (
                f"result = await self.db.execute({query})\n"
                "return result.scalar_one_or_none()"
            )
        return f"result = await self.db.execute({query})\nreturn result.scalars().all()"

    def _translate_where(self, where_text: str, entity: str) -> str:
        if not where_text:
            return ""
        translated = where_text
        translated = re.sub(rf"\b\w+\.([A-Za-z0-9_]+)\b", lambda m: f"{entity}.{self._camel_to_snake(m.group(1))}", translated)
        translated = re.sub(r":([A-Za-z0-9_]+)", lambda m: self._camel_to_snake(m.group(1)), translated)
        translated = translated.replace(" = ", " == ")
        translated = translated.replace(" AND ", ", ")
        translated = translated.replace(" and ", ", ")
        return translated

    def _translate_order(self, order_text: str, entity: str) -> str:
        if not order_text:
            return ""
        match = re.match(r"([A-Za-z0-9_]+)(Desc|Asc)?", order_text.strip(), re.IGNORECASE)
        if not match:
            return ""
        column = self._camel_to_snake(match.group(1))
        direction = (match.group(2) or "").lower()
        expr = f"{entity}.{column}"
        if direction == "desc":
            expr += ".desc()"
        elif direction == "asc":
            expr += ".asc()"
        return expr

    def _camel_to_snake(self, name: str) -> str:
        return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
