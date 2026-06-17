# Frontend Development Plan - Beverage Distributor System

## 📱 Overview

Simple, modern web frontend for the beverage distributor REST API.
- **Framework:** React 18+ with Vite
- **Styling:** Tailwind CSS (utility-first, production-ready)
- **State Management:** React Hooks + Context API (no Redux needed)
- **Routing:** React Router v6
- **HTTP Client:** Axios with interceptors
- **Styling Components:** Headless UI for accessible components

---

## 🏗️ Architecture

```
frontend/
├── public/
│   ├── favicon.ico
│   └── index.html
├── src/
│   ├── components/
│   │   ├── common/
│   │   │   ├── Header.jsx
│   │   │   ├── Footer.jsx
│   │   │   ├── Navigation.jsx
│   │   │   ├── LoadingSpinner.jsx
│   │   │   ├── ErrorAlert.jsx
│   │   │   └── Toast.jsx
│   │   ├── product/
│   │   │   ├── ProductList.jsx
│   │   │   ├── ProductCard.jsx
│   │   │   ├── SearchBar.jsx
│   │   │   └── CategoryFilter.jsx
│   │   ├── cart/
│   │   │   ├── Cart.jsx
│   │   │   ├── CartItem.jsx
│   │   │   ├── CartSummary.jsx
│   │   │   └── CartFloatingButton.jsx
│   │   ├── order/
│   │   │   ├── Checkout.jsx
│   │   │   ├── CustomerForm.jsx
│   │   │   ├── OrderReview.jsx
│   │   │   ├── OrderConfirmation.jsx
│   │   │   ├── OrderDetails.jsx
│   │   │   └── OrderHistory.jsx
│   │   └── admin/
│   │       ├── Dashboard.jsx
│   │       └── StatsCards.jsx
│   ├── pages/
│   │   ├── HomePage.jsx
│   │   ├── CatalogPage.jsx
│   │   ├── CartPage.jsx
│   │   ├── CheckoutPage.jsx
│   │   ├── OrderDetailsPage.jsx
│   │   ├── OrderHistoryPage.jsx
│   │   ├── DashboardPage.jsx
│   │   └── NotFoundPage.jsx
│   ├── services/
│   │   ├── api.js (Axios instance)
│   │   ├── productService.js
│   │   ├── orderService.js
│   │   └── idempotencyService.js
│   ├── hooks/
│   │   ├── useProducts.js
│   │   ├── useOrders.js
│   │   ├── useCart.js
│   │   └── useFetch.js (generic)
│   ├── context/
│   │   ├── CartContext.jsx
│   │   ├── AuthContext.jsx (future)
│   │   └── NotificationContext.jsx
│   ├── styles/
│   │   └── globals.css (Tailwind imports)
│   ├── utils/
│   │   ├── formatters.js (currency, dates)
│   │   ├── validators.js (form validation)
│   │   └── constants.js (API endpoints, UI constants)
│   ├── App.jsx (Router setup)
│   └── main.jsx (Entry point)
├── .env.example
├── .gitignore
├── package.json
├── vite.config.js
├── tailwind.config.js
└── postcss.config.js
```

---

## 📋 Detailed Implementation Plan

### **Phase 1: Project Setup**

#### **1.1 Initialize React Project**
```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install
```

#### **1.2 Install Dependencies**
```bash
# Core dependencies
npm install react-router-dom axios

# Styling
npm install -D tailwindcss postcss autoprefixer
npm install @headlessui/react @heroicons/react

# Development
npm install -D vitest @testing-library/react @testing-library/jest-dom
npm install -D cypress
```

#### **1.3 Configure Tailwind CSS**
```javascript
// tailwind.config.js
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#3B82F6',
        secondary: '#10B981',
      },
    },
  },
  plugins: [],
}
```

#### **1.4 Setup Environment Variables**
```bash
# .env.example
VITE_API_BASE_URL=http://localhost:8000
VITE_API_TIMEOUT=30000

# .env (development)
VITE_API_BASE_URL=http://localhost:8000
```

---

### **Phase 2: Core Components**

#### **2.1 API Client Setup** - `services/api.js`
```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: import.meta.env.VITE_API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for Idempotency-Key
api.interceptors.request.use((config) => {
  if (config.method === 'post') {
    config.headers['Idempotency-Key'] = generateIdempotencyKey();
  }
  return config;
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle errors consistently
    return Promise.reject({
      message: error.response?.data?.detail || error.message,
      status: error.response?.status,
    });
  }
);

export default api;
```

#### **2.2 Service Layers** - `services/*.js`

**Product Service:**
```javascript
// services/productService.js
export const fetchProducts = (skip = 0, limit = 20, categoria = null) => {
  // GET /api/v1/produtos?skip=0&limit=20&categoria=...
};

export const fetchProduct = (id) => {
  // GET /api/v1/produtos/{id}
};
```

**Order Service:**
```javascript
// services/orderService.js
export const createOrder = (cliente_id, items) => {
  // POST /api/v1/pedidos with Idempotency-Key
};

export const fetchOrder = (id) => {
  // GET /api/v1/pedidos/{id}
};

export const fetchOrders = (cliente_id = null, skip = 0, limit = 20) => {
  // GET /api/v1/pedidos?cliente_id=...&skip=...&limit=...
};
```

#### **2.3 Custom Hooks** - `hooks/*.js`

**useCart Hook:**
```javascript
// hooks/useCart.js
export const useCart = () => {
  // State: cart items stored in localStorage
  // Methods: addItem(), removeItem(), updateQuantity(), clear()
  // Persists to localStorage on changes
  // Returns: cart, addItem, removeItem, updateQuantity, clear, total
};
```

**useProducts Hook:**
```javascript
// hooks/useProducts.js
export const useProducts = (skip = 0, limit = 20, categoria = null) => {
  // Fetches products from API
  // Returns: products, loading, error, pagination
};
```

**useOrders Hook:**
```javascript
// hooks/useOrders.js
export const useOrders = (cliente_id = null) => {
  // Fetches orders from API
  // Returns: orders, loading, error
};
```

---

### **Phase 3: Pages**

#### **3.1 Home Page** - Simple landing with navigation
- Hero section
- Quick link to catalog
- Recent orders (if logged in)

#### **3.2 Catalog Page** - Product browsing
```
┌─────────────────────────────────────┐
│ Header: Search | Filter by Category │
├─────────────────────────────────────┤
│ [Product Card] [Product Card] [Card]│
│ [Product Card] [Product Card] [Card]│
│ [Product Card] [Product Card] [Card]│
├─────────────────────────────────────┤
│ « Prev [1] [2] [3] Next »            │
└─────────────────────────────────────┘
```

**ProductCard Component:**
```
┌──────────────────┐
│                  │
│   Product Name   │ Category
│   R$ 15.99       │ Stock: 100
│                  │
│  [Add to Cart] ──│ In Stock
└──────────────────┘
```

#### **3.3 Cart Page** - Review items
```
┌─────────────────────────────────────┐
│ Your Shopping Cart                  │
├─────────────────────────────────────┤
│ Product Name      Qty  R$ 15.99     │
│ [-] 5 [+]              R$ 79.95  [X]│
│                                     │
│ Product Name 2    Qty  R$ 8.99      │
│ [-] 3 [+]              R$ 26.97  [X]│
├─────────────────────────────────────┤
│ Subtotal:                 R$ 106.92 │
│                                     │
│ [Continue Shopping]  [Checkout]     │
└─────────────────────────────────────┘
```

#### **3.4 Checkout Page** - Order placement
```
Step 1: Customer Info
┌──────────────────────┐
│ Customer ID: [____]  │
│ Name: [____________] │
└──────────────────────┘
      [Next]

Step 2: Review Order
├──────────────────────────────────────┤
│ Order Summary                        │
│ Items: 8                   R$ 106.92 │
│                                     │
│ [Back]                    [Confirm] │
└──────────────────────────────────────┘

Step 3: Confirmation
┌──────────────────────────────────────┐
│ ✓ Order Created Successfully!        │
│                                      │
│ Order ID: #12345                     │
│ Status: PENDENTE                     │
│                                      │
│ [View Order Details] [Continue Shop] │
└──────────────────────────────────────┘
```

#### **3.5 Order History Page** - List customer orders
```
┌─────────────────────────────────────┐
│ My Orders                           │
│ Filter by Customer ID: [_______]    │
├─────────────────────────────────────┤
│ Order #12345  | PENDENTE | R$ 106.92│ ← Click to view details
│ Order #12344  | PENDENTE | R$ 45.00 │
│ Order #12343  | PENDENTE | R$ 78.50 │
├─────────────────────────────────────┤
│ « Prev [1] [2] [3] Next »            │
└─────────────────────────────────────┘
```

#### **3.6 Order Details Page** - View full order
```
┌──────────────────────────────────────┐
│ Order #12345                         │
│ Created: 2026-06-17 15:24:35         │
│ Status: PENDENTE                     │
├──────────────────────────────────────┤
│ Customer ID: 1                       │
│ Items:                               │
│   - Cerveja Premium x5 @ R$15.99 = R$79.95
│   - Refrigerante x3 @ R$5.99 = R$17.97
├──────────────────────────────────────┤
│ Subtotal:            R$ 97.92        │
│ TOTAL:               R$ 97.92        │
├──────────────────────────────────────┤
│ [Edit]              [Cancel Order]   │
└──────────────────────────────────────┘
```

---

### **Phase 4: State Management**

#### **4.1 Cart Context** - Global cart state
```javascript
// context/CartContext.jsx
<CartProvider>
  {/* Children can use useCart hook */}
</CartProvider>

// Usage:
const { cart, addItem, removeItem } = useCart();
```

#### **4.2 Toast Notifications** - User feedback
```javascript
// Show success: "Order created successfully!"
// Show error: "Product not found"
// Show loading: "Creating order..."
```

---

### **Phase 5: Styling**

#### **Color Scheme**
```
Primary Blue:   #3B82F6  (Actions, highlights)
Success Green:  #10B981  (Confirmations)
Warning Yellow: #F59E0B  (Warnings)
Error Red:      #EF4444  (Errors)
Gray:           #6B7280  (Text, borders)
```

#### **Typography**
- Headers: Bold, large sizes
- Body: Clear, readable sans-serif
- Prices: Bold, accent color

#### **Responsive Breakpoints**
- Mobile: 320px - 640px (1 column)
- Tablet: 640px - 1024px (2 columns)
- Desktop: 1024px+ (3-4 columns)

---

### **Phase 6: Testing**

#### **Component Tests**
```javascript
// test ProductCard.test.jsx
describe('ProductCard', () => {
  test('renders product name and price', () => {});
  test('add to cart button works', () => {});
  test('shows out of stock state', () => {});
});
```

#### **Integration Tests**
```javascript
// test/integration/checkout.test.jsx
describe('Checkout Flow', () => {
  test('user can create order with idempotency', () => {});
  test('duplicate order returns same result', () => {});
  test('validation errors shown correctly', () => {});
});
```

#### **E2E Tests** - Cypress
```javascript
// cypress/e2e/order-flow.cy.js
describe('Complete Order Flow', () => {
  it('user can browse products and create order', () => {
    cy.visit('http://localhost:5173');
    cy.get('[data-testid="browse-products"]').click();
    cy.get('[data-testid="add-to-cart"]').first().click();
    cy.get('[data-testid="checkout"]').click();
    // ... assertions
  });
});
```

---

### **Phase 7: Deployment**

#### **7.1 Production Build**
```bash
npm run build
# Creates dist/ folder with optimized assets
```

#### **7.2 Docker Container** - `Dockerfile`
```dockerfile
FROM node:18-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

#### **7.3 Docker Compose** - Update existing
```yaml
services:
  db:
    # ... existing config

  api:
    # ... backend (port 8000)

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    environment:
      - VITE_API_BASE_URL=http://api:8000
    depends_on:
      - api
```

---

## 📁 Frontend Directory Structure Summary

```
frontend/
├── src/
│   ├── components/       (Reusable UI components)
│   ├── pages/           (Full page components)
│   ├── services/        (API clients)
│   ├── hooks/           (Custom React hooks)
│   ├── context/         (Global state)
│   ├── styles/          (CSS & Tailwind)
│   ├── utils/           (Helper functions)
│   ├── App.jsx          (Main router)
│   └── main.jsx         (Entry point)
├── public/              (Static assets)
├── tests/               (Test files)
├── .env.example
├── package.json
├── vite.config.js
└── tailwind.config.js
```

---

## 🚀 User Workflows

### **1. Browse & Order**
```
Home → Catalog (search/filter) → Add to Cart → Cart Review → Checkout → Confirmation
```

### **2. View Order History**
```
Account → My Orders (filter by ID) → Order Details → Track Status
```

### **3. Admin Dashboard**
```
Dashboard → View Recent Orders → Check Inventory → See Metrics
```

---

## 🔗 API Integration Checklist

- [x] GET /health (app status)
- [x] GET /api/v1/produtos (product list)
- [x] GET /api/v1/produtos/{id} (product detail)
- [x] POST /api/v1/pedidos (create order with Idempotency-Key)
- [x] GET /api/v1/pedidos (order history)
- [x] GET /api/v1/pedidos/{id} (order details)

---

## 💾 Data Storage

### **Frontend Storage**
```javascript
// localStorage
{
  "cart": [
    { "produto_id": 1, "quantidade": 5, "preco_unitario": 15.99 },
    { "produto_id": 2, "quantidade": 3, "preco_unitario": 5.99 }
  ],
  "lastVisited": "2026-06-17T15:24:35Z"
}
```

### **Backend API**
- All data stored in PostgreSQL
- Cart only in frontend (localStorage)
- Orders persisted when submitted

---

## 📊 Estimated Implementation Time

| Phase | Task | Effort |
|-------|------|--------|
| 1 | Setup & Dependencies | 30 min |
| 2 | Core Components | 2 hours |
| 3 | Pages & Layout | 3 hours |
| 4 | State Management | 1 hour |
| 5 | Styling & Polish | 2 hours |
| 6 | Testing | 3 hours |
| 7 | Deployment | 1 hour |
| **Total** | **Full Frontend** | **~13 hours** |

---

## ✅ Definition of Done - Frontend

- [x] All pages responsive (mobile, tablet, desktop)
- [x] API integration complete
- [x] Cart functionality working
- [x] Order creation with idempotency
- [x] Order history and details viewing
- [x] Error handling & user feedback
- [x] Loading states
- [x] Tests > 70% coverage
- [x] Production-ready build
- [x] Docker container ready
- [x] Documentation complete

---

## 📝 Next Steps

1. **Setup Phase 1** - Initialize React project with Vite
2. **Build Phase 2** - Create API client and services
3. **Implement Phase 3** - Build pages and components
4. **Test Phase 4-6** - State management, styling, and testing
5. **Deploy Phase 7** - Docker and production build

All backend endpoints are ready! Frontend just needs to consume them. 🎉
