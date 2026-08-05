--
-- PostgreSQL database dump
--

\restrict fixture_restrict_key

-- Dumped from database version 16.14
-- Dumped by pg_dump version 16.14

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: audit; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA audit;


--
-- Name: sales; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA sales;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: Order Events; Type: TABLE; Schema: audit; Owner: -
--

CREATE TABLE audit."Order Events" (
    event_id bigint NOT NULL,
    tenant_id bigint NOT NULL,
    order_id bigint NOT NULL,
    "Event Type" character varying(40) DEFAULT 'created'::character varying NOT NULL,
    details jsonb
);


--
-- Name: customers; Type: TABLE; Schema: sales; Owner: -
--

CREATE TABLE sales.customers (
    tenant_id bigint NOT NULL,
    customer_id bigint NOT NULL,
    display_name character varying(120) NOT NULL,
    nickname text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: orders; Type: TABLE; Schema: sales; Owner: -
--

CREATE TABLE sales.orders (
    tenant_id bigint NOT NULL,
    order_id bigint NOT NULL,
    customer_id bigint NOT NULL,
    note text DEFAULT 'fixture note'::text,
    total_amount numeric(12,2) DEFAULT 0.00 NOT NULL
);


--
-- Name: Order Events order_events_pkey; Type: CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit."Order Events"
    ADD CONSTRAINT order_events_pkey PRIMARY KEY (event_id);


--
-- Name: customers customers_pkey; Type: CONSTRAINT; Schema: sales; Owner: -
--

ALTER TABLE ONLY sales.customers
    ADD CONSTRAINT customers_pkey PRIMARY KEY (tenant_id, customer_id);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: sales; Owner: -
--

ALTER TABLE ONLY sales.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (tenant_id, order_id);


--
-- Name: Order Events order_events_order_fk; Type: FK CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit."Order Events"
    ADD CONSTRAINT order_events_order_fk FOREIGN KEY (tenant_id, order_id) REFERENCES sales.orders(tenant_id, order_id);


--
-- Name: orders orders_customer_fk; Type: FK CONSTRAINT; Schema: sales; Owner: -
--

ALTER TABLE ONLY sales.orders
    ADD CONSTRAINT orders_customer_fk FOREIGN KEY (tenant_id, customer_id) REFERENCES sales.customers(tenant_id, customer_id);


--
-- PostgreSQL database dump complete
--

\unrestrict fixture_restrict_key
