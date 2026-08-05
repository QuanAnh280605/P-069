-- ============================================================================
-- SQL DUMP TEST FILE (PostgreSQL & MySQL Compatible DDLs)
-- Purpose: Test DDL parsing for Schema Metadata Extraction
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table 1: users (Thông tin người dùng)
-- ----------------------------------------------------------------------------
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index cho tìm kiếm email nhanh
CREATE INDEX idx_users_email ON users(email);


-- ----------------------------------------------------------------------------
-- Table 2: categories (Danh mục sản phẩm)
-- ----------------------------------------------------------------------------
CREATE TABLE categories (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL,
    description TEXT,
    parent_id INT DEFAULT NULL
);

-- Foreign key tự tham chiếu (Self-referencing Foreign Key)
ALTER TABLE categories 
ADD CONSTRAINT fk_categories_parent 
FOREIGN KEY (parent_id) REFERENCES categories(category_id) 
ON DELETE SET NULL;


-- ----------------------------------------------------------------------------
-- Table 3: products (Sản phẩm)
-- ----------------------------------------------------------------------------
CREATE TABLE products (
    product_id INT PRIMARY KEY,
    sku VARCHAR(50) NOT NULL UNIQUE,
    product_name VARCHAR(200) NOT NULL,
    category_id INT NOT NULL,
    price DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    stock_quantity INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'DRAFT',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_products_category FOREIGN KEY (category_id) REFERENCES categories(category_id)
);

CREATE INDEX idx_products_category_status ON products(category_id, status);


-- ----------------------------------------------------------------------------
-- Table 4: orders (Đơn hàng)
-- ----------------------------------------------------------------------------
CREATE TABLE orders (
    order_id BIGINT PRIMARY KEY,
    user_id INT NOT NULL,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_amount DECIMAL(15, 2) NOT NULL,
    shipping_address TEXT NOT NULL,
    status VARCHAR(30) DEFAULT 'PENDING'
);

ALTER TABLE orders 
ADD CONSTRAINT fk_orders_user 
FOREIGN KEY (user_id) REFERENCES users(user_id);


-- ----------------------------------------------------------------------------
-- Table 5: order_items (Chi tiết đơn hàng - Composite Primary Key)
-- ----------------------------------------------------------------------------
CREATE TABLE order_items (
    order_id BIGINT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    unit_price DECIMAL(12, 2) NOT NULL,
    subtotal DECIMAL(15, 2) NOT NULL,
    PRIMARY KEY (order_id, product_id),
    CONSTRAINT fk_items_order FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    CONSTRAINT fk_items_product FOREIGN KEY (product_id) REFERENCES products(product_id)
);