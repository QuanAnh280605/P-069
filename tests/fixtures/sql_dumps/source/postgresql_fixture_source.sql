CREATE SCHEMA sales;
CREATE SCHEMA audit;

CREATE TABLE sales.customers (
    tenant_id bigint NOT NULL,
    customer_id bigint NOT NULL,
    display_name character varying(120) NOT NULL,
    nickname text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT customers_pkey PRIMARY KEY (tenant_id, customer_id)
);

CREATE TABLE sales.orders (
    tenant_id bigint NOT NULL,
    order_id bigint NOT NULL,
    customer_id bigint NOT NULL,
    note text DEFAULT 'fixture note',
    total_amount numeric(12,2) DEFAULT 0.00 NOT NULL,
    CONSTRAINT orders_pkey PRIMARY KEY (tenant_id, order_id),
    CONSTRAINT orders_customer_fk FOREIGN KEY (tenant_id, customer_id)
        REFERENCES sales.customers (tenant_id, customer_id)
);

CREATE TABLE audit."Order Events" (
    event_id bigint NOT NULL,
    tenant_id bigint NOT NULL,
    order_id bigint NOT NULL,
    "Event Type" character varying(40) DEFAULT 'created' NOT NULL,
    details jsonb,
    CONSTRAINT order_events_pkey PRIMARY KEY (event_id)
);

ALTER TABLE ONLY audit."Order Events"
    ADD CONSTRAINT order_events_order_fk FOREIGN KEY (tenant_id, order_id)
    REFERENCES sales.orders (tenant_id, order_id);
