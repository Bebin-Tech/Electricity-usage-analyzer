# Database schema

`schema.sql` creates six normalized MySQL tables. Alternatively, `python manage.py init-db` creates the same entities from the SQLAlchemy definitions. Use either initialization method on a fresh database, not both. Application-managed defaults populate creation timestamps and account flags; raw SQL account inserts are not supported. Registration hashes passwords.

```mermaid
erDiagram
    users ||--o{ readings : owns
    users ||--o{ appliances : owns
    users ||--o{ prediction_history : generates
    users ||--o{ uploaded_datasets : imports
    users {
        int id PK
        string email UK
        string name
        string password_hash
        boolean is_admin
        boolean active
        datetime created_at
    }
    readings {
        int id PK
        int user_id FK
        date date "unique with user_id"
        float kwh
        string source
    }
    appliances {
        int id PK
        int user_id FK
        string name
        float watts
        float hours_per_day
        int quantity
    }
    prediction_history {
        int id PK
        int user_id FK
        datetime created_at
        text result_json
    }
    uploaded_datasets {
        int id PK
        int user_id FK
        string filename
        int row_count
        datetime uploaded_at
    }
    tariff_settings {
        int id PK
        string name
        float rate_per_kwh
        float fixed_charge
        string currency
    }
```

`tariff_settings` stores a platform-wide active configuration at ID 1. It has no user foreign key because it is shared and administrator-managed. Bills use the active configuration at calculation time. Prediction history stores immutable model-output snapshots; it does not pretend to be a relational table of measured readings. Uploaded dataset metadata is retained after the raw CSV is processed and discarded.

User/date uniqueness protects against concurrent duplicate inserts. Foreign keys prevent orphan records. User data is isolated by authenticated ownership checks in the service; MySQL does not provide row-level security here. User accounts are deactivated to preserve history. Numeric database checks supplement Pydantic range and finite-value validation.
