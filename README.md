# Rivyou — Product Search API

A Django REST API built as a Backend Engineer Intern assignment, implementing a product search engine with a custom multi-tier relevance ranking algorithm, fuzzy fallback search, JWT authentication, and dual-database architecture using PostgreSQL and MongoDB Atlas.

---

## ✦ Highlights

> These are the core engineering decisions that drive this project.

| # | What | Why it matters |
|---|------|----------------|
| 🥇 | **3-Tier Relevance Ranking Algorithm** | The heart of the assignment — fully implemented. Scores every result between 0.1–1.0 across three semantic tiers so the most relevant products always surface first. |
| 🔍 | **Fuzzy Search Fallback** | Powered by `thefuzz`. When exact matching returns zero results, fuzzy matching kicks in automatically to handle typos and near-matches. |
| 🔐 | **JWT Auth with Token Blacklisting** | Logout is real — tokens are blacklisted server-side so invalidated sessions cannot be reused. |
| 🍃 | **MongoDB Integration** | Search queries are logged to MongoDB Atlas, and per-user search history is stored and retrievable via a dedicated endpoint. |
| ⚡ | **GIN Index on Tags ArrayField** | PostgreSQL `ArrayField` for product tags is indexed with a GIN index, making tag-based lookups fast at scale. |
| 📖 | **Swagger UI** | Full interactive API documentation available at `/api/docs/` — no Postman setup required. |
| 🧪 | **5 Unit Tests** | Covers the search ranking tiers and authentication flows to validate core business logic. |

---

## Features

- User registration and login with JWT access/refresh tokens
- Secure logout with server-side token blacklisting
- Product search with query parameter support (`q`, `page`, `page_size`, `category_filter`)
- 3-tier relevance scoring — category → tags → name/description
- Fuzzy search fallback using `thefuzz` for typo tolerance
- Per-user search history stored in MongoDB Atlas
- Global search analytics endpoint
- GIN-indexed `ArrayField` for efficient tag queries in PostgreSQL
- Paginated product listing by category
- Product detail retrieval by ID
- Product creation endpoint
- Swagger/OpenAPI documentation via `drf-spectacular`
- Environment-based configuration via `.env`

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Framework | Django 6 |
| API Layer | Django REST Framework (DRF) |
| Primary Database | PostgreSQL |
| Secondary Database | MongoDB Atlas |
| Authentication | JWT (`djangorestframework-simplejwt`) |
| Fuzzy Matching | `thefuzz` |
| API Documentation | `drf-spectacular` (Swagger UI) |
| Task Queue | `django-rq` (installed, not active) |
| Environment Config | `python-decouple` / `.env` |

---

## Setup Instructions

### Prerequisites

- Python 3.11+
- PostgreSQL (running locally)
- `pip`

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/rivyou.git
cd rivyou
```

### 2. Create and Activate a Virtual Environment

```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
SECRET_KEY=your-django-secret-key
DEBUG=True

DB_NAME=rivyou_db
DB_USER=your_postgres_user
DB_PASSWORD=your_postgres_password
DB_HOST=localhost
DB_PORT=5432

MONGO_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net/rivyou
```

### 5. Run Migrations

```bash
python manage.py migrate
```

### 6. Seed the Database

```bash
python manage.py load_products
```

### 7. Start the Development Server

```bash
python manage.py runserver
```

The API will be available at `http://127.0.0.1:8000/`.
Swagger UI is at `http://127.0.0.1:8000/api/docs/`.

---

## API Endpoints

| Method | Endpoint | Auth Required | Description |
|--------|----------|:---:|-------------|
| `POST` | `/api/auth/register/` | No | Register a new user account |
| `POST` | `/api/auth/login/` | No | Log in and receive JWT tokens |
| `POST` | `/api/auth/logout/` | Yes | Log out and blacklist the refresh token |
| `GET` | `/api/auth/search-history/` | Yes | Retrieve the current user's search history from MongoDB |
| `GET` | `/api/analytics/search-history/` | Yes | Alias for `/api/auth/search-history/` — per-user search history |
| `GET` | `/api/products/search/?q=<query>&page=1&page_size=20&category_filter=` | Yes | Search products with ranked results and optional category filter |
| `GET` | `/api/products/<id>/` | Yes | Retrieve a single product by its ID |
| `GET` | `/api/products/category/<category>/` | Yes | List all products in a given category, paginated |
| `POST` | `/api/products/` | Yes | Create a new product |
| `GET` | `/api/docs/` | No | Interactive Swagger UI documentation |

---

## Search Ranking Logic

The ranking algorithm is the core deliverable of this assignment. Every product returned by the search endpoint carries a `relevance_score` between `0.0` and `1.0`. Results are sorted descending by this score so the most semantically relevant products always appear first.

### Tier Structure

```
Score Range    Tier    Match Condition
──────────────────────────────────────────────────────────────────
0.70 – 1.00   Tier 1  Product's category name contains the query
0.40 – 0.69   Tier 2  Product's tags array contains the query term
0.10 – 0.39   Tier 3  Product name or description contains the query
```

### Tier 1 — Category Match (Score: 0.70–1.00)

The highest priority tier. If the product's **category name** contains the search query, it is considered a direct category hit and returned first. These are the products the user is most likely looking for.

**Example:** searching `"smartphone"` → all products in the `Smartphones` category receive a Tier 1 score and appear at the top of results.

### Tier 2 — Tag Match (Score: 0.40–0.69)

If a product's **tags** (stored as a PostgreSQL `ArrayField`, GIN-indexed) contain the query term, it is considered related content. Products in adjacent categories that are tagged with the query term — such as charger accessories tagged `smartphone` — are surfaced here.

**Example:** searching `"smartphone"` → charger and phone cover listings tagged with `smartphone` appear after the Smartphone category results.

### Tier 3 — Name / Description Match (Score: 0.10–0.39)

The broadest tier. If the query term appears in the **product name or description**, it receives a low but non-zero relevance score. This ensures no relevant product is completely omitted.

### Fuzzy Fallback

When the exact search across all three tiers returns **zero results**, the algorithm automatically falls back to fuzzy matching using `thefuzz`. It computes string similarity ratios against product names and returns the closest matches above a configurable threshold. This handles common typos and near-matches (e.g., `"smarphone"` still finds `Smartphones`).

### Worked Example

```
Query: "smartphone"

Tier 1 (score ≥ 0.70):  ~330 products  — category: Smartphones
Tier 2 (score ≥ 0.40):  ~100 products  — chargers, covers, earphones tagged "smartphone"
Tier 3 (score ≥ 0.10):  variable       — products mentioning "smartphone" in name/description
Fuzzy fallback:          not triggered  — exact results were found
```

---

## Running Tests

```bash
python manage.py test products
```

The test suite covers:

- Tier 1, 2, and 3 ranking score assignment
- Fuzzy fallback activation on zero exact results
- JWT registration and login flows

---

## Example Search Response

`GET /api/products/search/?q=smartphone&page=1&page_size=2`

```json
{
  "total_results": 430,
  "total_pages": 22,
  "page": 1,
  "search_type": "exact",
  "results": [
    {
      "id": 14,
      "product_name": "Samsung Galaxy S24 Ultra",
      "product_description": "Flagship Android smartphone with a 200MP camera, S Pen, and Snapdragon 8 Gen 3.",
      "category": "Smartphones",
      "tags": ["smartphone", "android", "samsung"],
      "relevance_score": 0.91,
      "rank_reason": "category match",
      "created_at": "2024-11-03T08:22:11.504Z"
    },
    {
      "id": 203,
      "product_name": "Anker 65W USB-C Charger",
      "product_description": "Compact GaN charger compatible with all major smartphones and laptops.",
      "category": "Chargers",
      "tags": ["smartphone", "fast-charge", "usb-c"],
      "relevance_score": 0.52,
      "rank_reason": "tag match",
      "created_at": "2024-11-05T14:09:37.120Z"
    }
  ]
}
```

---

## Notes

**Deployment**
The project is not deployed. Per the assignment requirements, it uses a local PostgreSQL instance, making a hosted deployment outside scope. That said, it can be deployed to Railway or Render with a single `DATABASE_URL` config change — the codebase is already structured for it.

**Redis / Caching**
`django-rq` is listed in `requirements.txt` and the project architecture is designed to support Redis-backed caching and background task queuing. It was intentionally left inactive in this submission to keep the codebase clean and focused on the core assignment requirements — adding it would be straightforward.
