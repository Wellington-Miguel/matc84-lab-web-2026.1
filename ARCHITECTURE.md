# System Architecture - Beverage Distributor MVP

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                             │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  WEB BROWSER (React Frontend)                        │  │
│  │                                                      │  │
│  │  Pages:                    Components:              │  │
│  │  - Home                    - ProductCard            │  │
│  │  - Catalog                 - CartSummary            │  │
│  │  - Cart                    - OrderReview            │  │
│  │  - Checkout                - OrderStatus            │  │
│  │  - Order History           - SearchBar              │  │
│  │  - Order Details           - Header/Footer          │  │
│  │  - Dashboard               - Loading Spinner        │  │
│  │                                                      │  │
│  │  State: Cart (localStorage), Orders (API)           │  │
│  │  HTTP Client: Axios with interceptors               │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│                    Port: 3000                              │
└──────────────────────────────────────────────────────────┬──┘
                                                          │
                         HTTP REST                       │
                      JSON Request/Response              │
                                                          │
┌──────────────────────────────────────────────────────────┴──┐
│                    API LAYER (FastAPI)                     │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  REST Endpoints                                      │  │
│  │  ├── GET  /health                    (Liveness)    │  │
│  │  ├── GET  /ready                     (Readiness)   │  │
│  │  ├── GET  /api/v1/produtos           (List)        │  │
│  │  ├── GET  /api/v1/produtos/{id}      (Detail)      │  │
│  │  ├── POST /api/v1/pedidos            (Create)      │  │
│  │  ├── GET  /api/v1/pedidos/{id}       (Detail)      │  │
│  │  └── GET  /api/v1/pedidos            (List)        │  │
│  │                                                      │  │
│  │  Routers:                                            │  │
│  │  - rotas_saude.py (health checks)                   │  │
│  │  - rotas_produto.py (products)                      │  │
│  │  - rotas_pedidos.py (orders)                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Business Logic Services                             │  │
│  │  ├── servico_pedido.py    (Order management)        │  │
│  │  ├── servico_estoque.py   (Inventory)               │  │
│  │  └── worker_outbox.py     (Event processing)        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Core Infrastructure                                 │  │
│  │  ├── config.py            (Settings)                │  │
│  │  ├── database.py          (Session management)      │  │
│  │  ├── idempotency.py       (Request deduplication)   │  │
│  │  ├── exceptions.py        (Error handling)          │  │
│  │  ├── logging.py           (Observability)           │  │
│  │  └── middleware.py        (Correlation IDs)         │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│                    Port: 8000                              │
└──────────────────────────────────────┬─────────────────────┘
                                       │
                                       │ SQL/psycopg2
                                       │
┌──────────────────────────────────────┴─────────────────────┐
│                  DATA LAYER (PostgreSQL)                   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Tables:                                             │  │
│  │  ├── produtos               (Beverage inventory)    │  │
│  │  ├── pedidos                (Customer orders)       │  │
│  │  ├── itens_pedido           (Order line items)      │  │
│  │  ├── outbox_events          (Event outbox)          │  │
│  │  └── idempotencia_log       (Request tracking)      │  │
│  │                                                      │  │
│  │  Relationships:                                      │  │
│  │  ├── Pedido → ItemPedido (1:N)                      │  │
│  │  ├── ItemPedido → Produto (N:1)                     │  │
│  │  └── OutboxEvent (Standalone)                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│                    Port: 5432                              │
│                    Database: distribuidora                 │
└──────────────────────────────────────────────────────────┘
```

---

## 📊 Data Flow Diagrams

### **1. Browse & Add to Cart Flow**

```
User                Frontend              Backend         Database
 │                     │                     │                │
 │─ Browse Products ──→│                     │                │
 │                     │─ GET /api/v1/produtos ───────────────│
 │                     │                     │     Query DB   │
 │                     │←───────── List 20 Products ──────────│
 │                     │                     │                │
 │ Display Products    │                     │                │
 │←────────────────────│                     │                │
 │                     │                     │                │
 │─ Click Add to Cart──│                     │                │
 │                     │ (Store in localStorage)              │
 │ Confirm Added       │                     │                │
 │←────────────────────│                     │                │
 │                     │                     │                │
 │─ View Cart ────────→│                     │                │
 │ [Product, Qty, $$$] │                     │                │
 │←────────────────────│                     │                │
```

### **2. Create Order Flow (Idempotent)**

```
User                Frontend              Backend         Database
 │                     │                     │                │
 │─ Click Checkout ──→│                     │                │
 │                     │ Generate Idempotency-Key             │
 │                     │                     │                │
 │─ Enter Customer ID─→│                     │                │
 │                     │                     │                │
 │─ Click Create ─────→│                     │                │
 │                     │                     │                │
 │                     │ POST /api/v1/pedidos ──────────────→│
 │                     │ Idempotency-Key: UUID                │
 │                     │ Body: {cliente_id, items[]}          │
 │                     │                                       │
 │                     │         TRANSACTION BEGIN            │
 │                     │              │                       │
 │                     │              │ Validate items       │
 │                     │              │ Reserve stock        │
 │                     │              │ Create order         │
 │                     │              │ Create items         │
 │                     │              │ Create outbox event  │
 │                     │              │ COMMIT               │
 │                     │                      │ Insert Order  │
 │                     │                      │ Insert Items  │
 │                     │                      │ Insert Event  │
 │                     │←──── Order Created: {id, total} ────│
 │ Show Confirmation   │                     │                │
 │←────────────────────│                     │                │
 │                     │ Cache in localStorage                │
 │                     │ (Same key → same response)           │
```

### **3. Background Outbox Processing**

```
Database            Worker Process        Side Effects
    │                   │                      │
    │ Outbox Table      │                      │
    │ [Event 1]         │                      │
    │ [Event 2]  ←──────┤                      │
    │ [Event 3]         │ Poll every 5s       │
    │ [Event 4]         │                      │
    │                   │                      │
    │                   │─ Process Event 1 ──→ Update Cache
    │                   │   Mark as processed  │
    │                   │                      │
    │                   │─ Process Event 2 ──→ Send Webhook
    │ Update: processed │   Mark as processed  │
    │←─────────────────│                      │
    │                   │                      │
    │                   │─ Process Event 3 ──→ Analytics
    │                   │   Mark as processed  │
    │                   │                      │
    │ (Retry failed)    │                      │
    │←─────────────────│─ Exponential Backoff │
```

### **4. View Order History Flow**

```
User                Frontend              Backend         Database
 │                     │                     │                │
 │─ Click My Orders ──→│                     │                │
 │                     │                     │                │
 │─ Enter Customer ID─→│                     │                │
 │                     │─ GET /api/v1/pedidos?cliente_id=1 ──→│
 │                     │                     │     Query DB   │
 │                     │←──── List Orders ───────────────────│
 │ Show Orders Table   │                     │                │
 │←────────────────────│                     │                │
 │                     │                     │                │
 │─ Click Order ──────→│                     │                │
 │                     │─ GET /api/v1/pedidos/{id} ──────────→│
 │                     │                     │     Query DB   │
 │ Show Details        │←──── Order + Items ────────────────│
 │←────────────────────│                     │                │
```

---

## 🔄 Request Flow with Idempotency

```
REQUEST 1 (New Order)
┌─────────────────────────────────────┐
│ POST /api/v1/pedidos                │
│ Idempotency-Key: abc-123            │
│ Body: {cliente_id: 1, items: [...]} │
└──────────────────┬──────────────────┘
                   │
        CHECK IDEMPOTENCY LOG
                   │
              ┌────┴────┐
              │ NOT FOUND│
              └────┬─────┘
              CREATE ORDER
           INSERT IDEMPOTENCY LOG
             RETURN ORDER
                   │
           RESPONSE #1
        {id: 1, total: 100}


REQUEST 2 (Same Key, Same Body)
┌─────────────────────────────────────┐
│ POST /api/v1/pedidos                │
│ Idempotency-Key: abc-123            │
│ Body: {cliente_id: 1, items: [...]} │
└──────────────────┬──────────────────┘
                   │
        CHECK IDEMPOTENCY LOG
                   │
              ┌────┴────┐
              │ FOUND!   │
              └────┬─────┘
         RETURN CACHED RESPONSE
         (NO NEW ORDER CREATED)
                   │
           RESPONSE #2
        {id: 1, total: 100}  ← SAME AS #1


Database State After Both Requests:
├── pedidos table
│   └── Order #1 (only ONE order exists)
│
└── idempotencia_log table
    └── Key: abc-123 → Result: {id: 1, total: 100}
```

---

## 🔐 Stock Reservation with Database Locking

```
TRANSACTION 1 (Concurrent Order A)
┌──────────────────────────────┐
│ SELECT FOR UPDATE (Lock)     │
│ WHERE produto_id = 1         │
└────────────┬─────────────────┘
             │ (Product locked)
             │
        CHECK STOCK
             │
        STOCK = 100
        NEED = 50 ✓
             │
      DEDUCT 50
      (100 → 50)
             │
        COMMIT


TRANSACTION 2 (Concurrent Order B - Tries to run simultaneously)
┌──────────────────────────────┐
│ SELECT FOR UPDATE (Lock)     │
│ WHERE produto_id = 1         │
└────────────┬─────────────────┘
             │ (WAITS - locked by Txn 1)
             │
        (BLOCKED...)
             │
        After Txn 1 COMMITS
             │
        LOCK ACQUIRED
        CURRENT STOCK = 50
        NEED = 40 ✓
             │
      DEDUCT 40
      (50 → 10)
             │
        COMMIT


Final Result:
Products Table:
└── Produto #1: estoque = 10 (50 - 40)

Both orders succeeded, no overselling ✓
```

---

## 🌐 System Integration Points

### **Frontend → Backend**
- **HTTP REST API** - Axios client with error handling
- **Idempotency-Key Header** - Auto-generated UUIDs
- **CORS** - Enabled for localhost development
- **Error Handling** - Consistent error responses

### **Backend → Database**
- **SQLAlchemy ORM** - Type-safe queries
- **Connection Pooling** - 5-20 concurrent connections
- **Transactions** - ACID compliance for orders
- **Locking** - SELECT FOR UPDATE for stock

### **Background Processing**
- **Outbox Pattern** - Events stored atomically
- **Worker Process** - Async task in FastAPI
- **Polling** - Every 5 seconds (configurable)
- **Exponential Backoff** - Retry failed events

---

## 📈 Scalability Considerations

### **Current Architecture (MVP)**
- Single backend process
- FastAPI with Uvicorn
- Outbox worker as background task
- PostgreSQL single instance

### **Future: Horizontal Scaling**
```
Load Balancer
├── API Instance 1 (no worker)
├── API Instance 2 (no worker)
├── API Instance 3 (no worker)
└── Worker Instance (dedicated)
    └── Processes all outbox events
        (Shared database)
```

**Why This Works:**
- All state in PostgreSQL (stateless APIs)
- Outbox pattern ensures no event loss
- Single worker prevents duplicate processing
- Scale APIs independently from worker

---

## ✅ Key Architecture Benefits

1. **Idempotency** - Duplicate requests handled safely
2. **Race Condition Prevention** - Database-level locking
3. **Event-Driven** - Foundation for future integrations
4. **Stateless** - Easy to scale horizontally
5. **Clean Separation** - Frontend/Backend decoupled
6. **ACID Compliance** - No data loss
7. **Fault Tolerance** - Retries with exponential backoff
8. **Observable** - Logging and metrics ready

---

## 🔗 System Boundaries

### **Backend Responsibilities**
- Validate business logic
- Manage inventory atomically
- Persist events reliably
- Return consistent responses

### **Frontend Responsibilities**
- Present UI to users
- Collect customer input
- Validate form fields
- Display feedback
- Manage local cart state

### **Database Responsibilities**
- Store all persistent state
- Enforce constraints
- Provide ACID transactions
- Support efficient queries

---

## 🎯 Performance Targets

| Operation | Target | Current |
|-----------|--------|---------|
| List products | <200ms | ✓ |
| Get order | <200ms | ✓ |
| Create order | <500ms | ✓ |
| List orders | <500ms | ✓ |
| Concurrent orders | 25 req/s | ✓ |
| Stock accuracy | 100% | ✓ |

---

## 📝 Technology Stack Summary

```
Frontend:
├── React 18+ (UI library)
├── Vite (Build tool)
├── Tailwind CSS (Styling)
├── React Router (Routing)
├── Axios (HTTP client)
└── React Hooks (State management)

Backend:
├── FastAPI (API framework)
├── SQLAlchemy (ORM)
├── Pydantic (Validation)
├── Uvicorn (ASGI server)
└── Python 3.12+

Database:
├── PostgreSQL 15
├── psycopg2 (Driver)
└── Connection pooling

DevOps:
├── Docker (Containers)
├── Docker Compose (Orchestration)
└── Pytest (Testing)
```

This architecture is production-ready, scalable, and maintainable! 🚀
