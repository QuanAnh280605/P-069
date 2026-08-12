CREATE TABLE customers (
    id BIGINT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    city VARCHAR(50) NULL,
    created_at DATETIME NOT NULL
);

CREATE TABLE products (
    id BIGINT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    price DECIMAL(12, 2) NOT NULL,
    status VARCHAR(20) NOT NULL
);

CREATE TABLE fact_orders (
    order_id BIGINT PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    store_id BIGINT NOT NULL,
    gross_amount DECIMAL(12, 2) NOT NULL,
    discount_amount DECIMAL(12, 2) NOT NULL DEFAULT 0,
    return_amount DECIMAL(12, 2) NOT NULL DEFAULT 0,
    cogs_amount DECIMAL(12, 2) NOT NULL,
    order_status VARCHAR(20) NOT NULL,
    is_test_order BOOLEAN NOT NULL DEFAULT FALSE,
    channel VARCHAR(30) NOT NULL,
    order_date DATETIME NOT NULL,
    customer_order_seq INT NOT NULL,
    CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE fact_order_items (
    line_item_id BIGINT PRIMARY KEY,
    order_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(12, 2) NOT NULL,
    is_test_order BOOLEAN NOT NULL DEFAULT FALSE,
    channel VARCHAR(30) NOT NULL,
    store_id BIGINT NOT NULL,
    order_date DATETIME NOT NULL,
    CONSTRAINT fk_items_order FOREIGN KEY (order_id) REFERENCES fact_orders(order_id),
    CONSTRAINT fk_items_product FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE fact_sessions (
    session_id BIGINT PRIMARY KEY,
    order_id BIGINT NULL,
    store_id BIGINT NOT NULL,
    channel VARCHAR(30) NOT NULL,
    device_type VARCHAR(20) NOT NULL,
    is_bot_traffic BOOLEAN NOT NULL DEFAULT FALSE,
    session_date DATETIME NOT NULL,
    CONSTRAINT fk_sessions_order FOREIGN KEY (order_id) REFERENCES fact_orders(order_id)
);

CREATE TABLE fact_carts (
    cart_id BIGINT PRIMARY KEY,
    customer_id BIGINT NULL,
    store_id BIGINT NOT NULL,
    channel VARCHAR(30) NOT NULL,
    device_type VARCHAR(20) NOT NULL,
    checkout_completed BOOLEAN NOT NULL DEFAULT FALSE,
    is_test_order BOOLEAN NOT NULL DEFAULT FALSE,
    cart_date DATETIME NOT NULL
);

CREATE TABLE payments (
    id BIGINT PRIMARY KEY,
    order_id BIGINT NOT NULL,
    payment_method VARCHAR(30) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    payment_date DATETIME NOT NULL,
    CONSTRAINT fk_payments_order FOREIGN KEY (order_id) REFERENCES fact_orders(order_id)
);
