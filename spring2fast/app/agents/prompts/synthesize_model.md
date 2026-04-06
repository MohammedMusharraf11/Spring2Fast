You are converting a Java JPA @Entity to a Python SQLAlchemy 2.0 ORM model.

RULES:
1. Use `Mapped[T]` and `mapped_column()` syntax (SQLAlchemy 2.0 style).
2. Map ALL JPA annotations precisely:
   - @Id @GeneratedValue → primary_key=True with autoincrement
   - @Column(unique=true, nullable=false, length=N) → mapped_column(unique=True, nullable=False, String(N))
   - @OneToMany(mappedBy="x") → relationship(back_populates="x")
   - @ManyToOne @JoinColumn(name="x") → mapped_column(ForeignKey("table.x")) + relationship
   - @ManyToMany → secondary table + relationship
   - @Enumerated(EnumType.STRING) → Enum column type
   - @CreationTimestamp → server_default=func.now()
   - @UpdateTimestamp → onupdate=func.now()
   - @Temporal(TemporalType.TIMESTAMP) → DateTime column
3. Map validation annotations to column constraints:
   - @NotNull → nullable=False
   - @Column(columnDefinition="TEXT") → Text type
4. Preserve the exact table name from @Table(name="x").
5. If @Table is missing, derive tablename from class name (snake_case, pluralized).
6. Include all imports at the top: sqlalchemy, orm, relationship, etc.
7. Output ONLY valid Python code. No markdown, no explanation, no extra text.

### JAVA SOURCE
{java_source}

### ENTITY CONTRACT (must satisfy all rules)
{contract_md}

### ALREADY GENERATED MODELS (use these for relationship references)
{existing_code}
