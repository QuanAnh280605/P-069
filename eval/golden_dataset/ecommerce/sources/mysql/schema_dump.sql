CREATE TABLE cities (
    city_id BIGINT PRIMARY KEY,
    city_name VARCHAR(50) NOT NULL,
    region_name VARCHAR(50) NOT NULL
);

CREATE TABLE customer_addresses (
    address_id BIGINT PRIMARY KEY,
    customer_id BIGINT NOT NULL UNIQUE,
    city_id BIGINT NOT NULL,
    address VARCHAR(200) NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_addresses_city FOREIGN KEY (city_id) REFERENCES cities(city_id)
);

CREATE TABLE customers (
    id BIGINT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    city VARCHAR(50) NULL,
    created_at DATETIME NOT NULL,
    default_address_id BIGINT NULL,
    CONSTRAINT fk_customers_address FOREIGN KEY (default_address_id) REFERENCES customer_addresses(address_id)
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
    delivered_time DATETIME NULL,
    is_delivered BOOLEAN NOT NULL DEFAULT FALSE,
    delivery_type VARCHAR(20) NULL,
    is_canceled BOOLEAN NOT NULL DEFAULT FALSE,
    cancel_reason VARCHAR(50) NULL,
    loyalty_card_id BIGINT NULL,
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
    is_canceled BOOLEAN NOT NULL DEFAULT FALSE,
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
    has_cart_addition BOOLEAN NOT NULL DEFAULT FALSE,
    reached_checkout BOOLEAN NOT NULL DEFAULT FALSE,
    completed_checkout BOOLEAN NOT NULL DEFAULT FALSE,
    session_duration_seconds INT NULL,
    utm_source VARCHAR(50) NULL,
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

CREATE TABLE dim_items (
    item_id BIGINT PRIMARY KEY,
    product_id BIGINT NOT NULL,
    item_name VARCHAR(100) NOT NULL,
    current_stock_quantity INT NOT NULL,
    min_stock_quantity INT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    in_stock BOOLEAN NOT NULL DEFAULT TRUE,
    category_id BIGINT NOT NULL,
    supplier_id BIGINT NOT NULL,
    store_id BIGINT NOT NULL,
    CONSTRAINT fk_items_product_ref FOREIGN KEY (product_id) REFERENCES products(id)
);
