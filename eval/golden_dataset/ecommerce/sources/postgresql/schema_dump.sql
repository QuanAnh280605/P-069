CREATE TABLE public.customers (
    id BIGINT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    city VARCHAR(50),
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE public.products (
    id BIGINT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    price NUMERIC(12, 2) NOT NULL,
    status VARCHAR(20) NOT NULL
);

CREATE TABLE public.fact_orders (
    order_id BIGINT PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES public.customers(id),
    store_id BIGINT NOT NULL,
    gross_amount NUMERIC(12, 2) NOT NULL,
    discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    return_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    cogs_amount NUMERIC(12, 2) NOT NULL,
    order_status VARCHAR(20) NOT NULL,
    is_test_order BOOLEAN NOT NULL DEFAULT FALSE,
    channel VARCHAR(30) NOT NULL,
    order_date TIMESTAMP NOT NULL,
    customer_order_seq INTEGER NOT NULL
);

CREATE TABLE public.fact_order_items (
    line_item_id BIGINT PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES public.fact_orders(order_id),
    product_id BIGINT NOT NULL REFERENCES public.products(id),
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL,
    is_test_order BOOLEAN NOT NULL DEFAULT FALSE,
    channel VARCHAR(30) NOT NULL,
    store_id BIGINT NOT NULL,
    order_date TIMESTAMP NOT NULL
);

CREATE TABLE public.fact_sessions (
    session_id BIGINT PRIMARY KEY,
    order_id BIGINT REFERENCES public.fact_orders(order_id),
    store_id BIGINT NOT NULL,
    channel VARCHAR(30) NOT NULL,
    device_type VARCHAR(20) NOT NULL,
    is_bot_traffic BOOLEAN NOT NULL DEFAULT FALSE,
    session_date TIMESTAMP NOT NULL
);

CREATE TABLE public.fact_carts (
    cart_id BIGINT PRIMARY KEY,
    customer_id BIGINT,
    store_id BIGINT NOT NULL,
    channel VARCHAR(30) NOT NULL,
    device_type VARCHAR(20) NOT NULL,
    checkout_completed BOOLEAN NOT NULL DEFAULT FALSE,
    is_test_order BOOLEAN NOT NULL DEFAULT FALSE,
    cart_date TIMESTAMP NOT NULL
);

CREATE TABLE public.payments (
    id BIGINT PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES public.fact_orders(order_id),
    payment_method VARCHAR(30) NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    payment_date TIMESTAMP NOT NULL
);
