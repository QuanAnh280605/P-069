CREATE DATABASE IF NOT EXISTS fixture_catalog CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE fixture_catalog;

CREATE TABLE `Customers` (
    `tenant_id` bigint NOT NULL,
    `customer_id` bigint NOT NULL,
    `display_name` varchar(120) NOT NULL,
    `nickname` varchar(120) DEFAULT NULL,
    `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`tenant_id`, `customer_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `orders` (
    `tenant_id` bigint NOT NULL,
    `order_id` bigint NOT NULL,
    `customer_id` bigint NOT NULL,
    `note` text,
    `total_amount` decimal(12,2) NOT NULL DEFAULT '0.00',
    PRIMARY KEY (`tenant_id`, `order_id`),
    CONSTRAINT `orders_customer_fk` FOREIGN KEY (`tenant_id`, `customer_id`)
        REFERENCES `Customers` (`tenant_id`, `customer_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `Order Events` (
    `event_id` bigint NOT NULL,
    `tenant_id` bigint NOT NULL,
    `order_id` bigint NOT NULL,
    `Event Type` varchar(40) NOT NULL DEFAULT 'created',
    `details` json DEFAULT NULL,
    PRIMARY KEY (`event_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE `Order Events`
    ADD CONSTRAINT `order_events_order_fk` FOREIGN KEY (`tenant_id`, `order_id`)
    REFERENCES `orders` (`tenant_id`, `order_id`);
