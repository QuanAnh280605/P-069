-- Deterministic SQLite data covering the nineteen ground-truth metrics.
-- Delivered set {1,2,3,4,7,8,10} averages 252/7 = 36.0 delivery hours.
-- 13 sessions including 1 bot row (no default bot filter): 8 completed
-- checkout, 10 reached checkout, 8 with cart addition; durations sum 3590s.

INSERT INTO cities VALUES
(1, 'Hà Nội', 'Bắc Bộ'),
(2, 'TP HCM', 'Nam Bộ'),
(3, 'Đà Nẵng', 'Trung Bộ'),
(4, 'Cần Thơ', 'Nam Bộ');

INSERT INTO customer_addresses VALUES
(1, 1, 1, 'Số 1 Phố Huế, Hoàn Kiếm', TRUE),
(2, 2, 2, '12 Nguyễn Huệ, Quận 1', TRUE),
(3, 3, 3, '45 Bạch Đằng, Hải Châu', TRUE),
(4, 4, 1, '9 Trần Duy Hưng, Cầu Giấy', TRUE),
(5, 5, 1, 'Phòng QA, Cầu Giấy', TRUE),
(6, 6, 4, '30 Hòa Bình, Ninh Kiều', TRUE);

INSERT INTO customers VALUES
(1, 'Khách hàng 1', 'customer1@example.test', 'Hà Nội', '2026-01-10 08:00:00', 1),
(2, 'Khách hàng 2', 'customer2@example.test', 'TP HCM', '2026-02-15 09:30:00', 2),
(3, 'Khách hàng 3', 'customer3@example.test', 'Đà Nẵng', '2026-03-20 10:15:00', 3),
(4, 'Khách hàng 4', 'customer4@example.test', 'Hà Nội', '2026-04-05 14:20:00', 4),
(5, 'Khách hàng test', 'customer5@example.test', NULL, '2026-05-01 07:00:00', 5),
(6, 'Khách hàng 6', 'customer6@example.test', 'Cần Thơ', '2026-06-01 07:00:00', 6);

INSERT INTO products VALUES
(101, 'Sản phẩm A', 'Điện tử', 500.00, 'active'),
(102, 'Sản phẩm B', 'Điện tử', 100.00, 'active'),
(103, 'Sản phẩm C', 'Gia dụng', 125.00, 'active'),
(104, 'Sản phẩm D', 'Thời trang', 100.00, 'active'),
(105, 'Sản phẩm test', 'Khác', 111.00, 'inactive');

INSERT INTO fact_orders VALUES
(1, 1, 1, 1000.00, 100.00, 0.00, 600.00, 'completed', FALSE, 'web', '2026-08-02 10:00:00', 1, '2026-08-03 10:00:00', TRUE, 'standard', FALSE, NULL, 101),
(2, 2, 1, 500.00, 0.00, 0.00, 300.00, 'completed', FALSE, 'mobile', '2026-08-03 11:00:00', 1, '2026-08-05 11:00:00', TRUE, 'express', FALSE, NULL, NULL),
(3, 1, 1, 300.00, 30.00, 0.00, 150.00, 'completed', FALSE, 'web', '2026-08-10 09:00:00', 2, '2026-08-11 09:00:00', TRUE, 'standard', FALSE, NULL, 101),
(4, 3, 2, 200.00, 0.00, 200.00, 120.00, 'returned', FALSE, 'marketplace', '2026-08-15 15:00:00', 1, '2026-08-18 15:00:00', TRUE, 'standard', FALSE, NULL, NULL),
(5, 4, 2, 400.00, 0.00, 0.00, 250.00, 'cancelled', FALSE, 'web', '2026-08-20 16:00:00', 1, NULL, FALSE, NULL, TRUE, 'customer_request', NULL),
(6, 5, 1, 999.00, 0.00, 0.00, 500.00, 'completed', TRUE, 'web', '2026-08-22 12:00:00', 1, NULL, FALSE, NULL, FALSE, NULL, NULL),
(7, 2, 1, 700.00, 70.00, 0.00, 400.00, 'completed', FALSE, 'mobile', '2026-09-01 08:00:00', 2, '2026-09-03 08:00:00', TRUE, 'express', FALSE, NULL, 202),
(8, 6, 2, 250.00, 0.00, 0.00, 100.00, 'completed', FALSE, 'marketplace', '2026-07-31 23:00:00', 1, '2026-08-01 23:00:00', TRUE, 'standard', FALSE, NULL, NULL),
(9, 3, 2, 350.00, 0.00, 50.00, 180.00, 'returned', FALSE, 'marketplace', '2026-09-05 14:00:00', 2, NULL, FALSE, NULL, FALSE, NULL, NULL),
(10, 1, 1, 150.00, 0.00, 0.00, 80.00, 'completed', FALSE, 'web', '2026-09-10 10:00:00', 3, '2026-09-10 22:00:00', TRUE, 'express', FALSE, NULL, NULL);

INSERT INTO fact_order_items VALUES
(1, 1, 101, 2, 500.00, FALSE, 'web', 1, '2026-08-02 10:00:00', FALSE),
(2, 2, 102, 1, 500.00, FALSE, 'mobile', 1, '2026-08-03 11:00:00', FALSE),
(3, 3, 101, 3, 100.00, FALSE, 'web', 1, '2026-08-10 09:00:00', FALSE),
(4, 4, 103, 1, 200.00, FALSE, 'marketplace', 2, '2026-08-15 15:00:00', FALSE),
(5, 5, 104, 4, 100.00, FALSE, 'web', 2, '2026-08-20 16:00:00', TRUE),
(6, 6, 105, 9, 111.00, TRUE, 'web', 1, '2026-08-22 12:00:00', FALSE),
(7, 7, 102, 7, 100.00, FALSE, 'mobile', 1, '2026-09-01 08:00:00', FALSE),
(8, 8, 103, 2, 125.00, FALSE, 'marketplace', 2, '2026-07-31 23:00:00', FALSE),
(9, 9, 103, 3, 116.67, FALSE, 'marketplace', 2, '2026-09-05 14:00:00', FALSE),
(10, 10, 101, 1, 150.00, FALSE, 'web', 1, '2026-09-10 10:00:00', FALSE);

INSERT INTO fact_sessions VALUES
(1, 1, 1, 'web', 'desktop', FALSE, '2026-08-02 09:30:00', TRUE, TRUE, TRUE, 420, 'organic'),
(2, 2, 1, 'mobile', 'mobile', FALSE, '2026-08-03 10:30:00', TRUE, TRUE, TRUE, 350, 'ads'),
(3, 3, 1, 'web', 'desktop', FALSE, '2026-08-10 08:30:00', TRUE, TRUE, TRUE, 500, 'organic'),
(4, 4, 2, 'marketplace', 'mobile', FALSE, '2026-08-15 14:30:00', FALSE, TRUE, TRUE, 600, 'email'),
(5, NULL, 2, 'web', 'desktop', FALSE, '2026-08-20 15:30:00', TRUE, FALSE, FALSE, 240, 'ads'),
(6, 7, 1, 'mobile', 'mobile', FALSE, '2026-09-01 07:30:00', TRUE, TRUE, TRUE, 410, 'organic'),
(7, 8, 2, 'marketplace', 'mobile', FALSE, '2026-07-31 22:30:00', FALSE, TRUE, TRUE, 180, NULL),
(8, 9, 2, 'marketplace', 'desktop', FALSE, '2026-09-05 13:30:00', TRUE, TRUE, TRUE, 300, 'email'),
(9, 10, 1, 'web', 'desktop', FALSE, '2026-09-10 09:30:00', FALSE, TRUE, TRUE, 280, 'organic'),
(10, NULL, 1, 'web', 'mobile', FALSE, '2026-08-25 13:00:00', TRUE, TRUE, FALSE, 150, 'ads'),
(11, NULL, 2, 'marketplace', 'mobile', FALSE, '2026-09-06 13:00:00', FALSE, TRUE, FALSE, 90, 'ads'),
(12, NULL, 1, 'mobile', 'desktop', FALSE, '2026-09-07 13:00:00', FALSE, FALSE, FALSE, 60, 'organic'),
(13, 6, 1, 'web', 'desktop', TRUE, '2026-08-22 11:30:00', TRUE, FALSE, FALSE, 10, 'bot');

INSERT INTO fact_carts VALUES
(1, 1, 1, 'web', 'desktop', TRUE, FALSE, '2026-08-02 09:00:00'),
(2, 2, 1, 'mobile', 'mobile', TRUE, FALSE, '2026-08-03 10:00:00'),
(3, 1, 1, 'web', 'desktop', TRUE, FALSE, '2026-08-10 08:00:00'),
(4, 3, 2, 'marketplace', 'mobile', TRUE, FALSE, '2026-08-15 14:00:00'),
(5, 4, 2, 'web', 'desktop', FALSE, FALSE, '2026-08-20 15:00:00'),
(6, 2, 1, 'mobile', 'mobile', TRUE, FALSE, '2026-09-01 07:00:00'),
(7, 6, 2, 'marketplace', 'mobile', TRUE, FALSE, '2026-07-31 22:00:00'),
(8, 3, 2, 'marketplace', 'desktop', FALSE, FALSE, '2026-09-05 13:00:00'),
(9, 1, 1, 'web', 'desktop', FALSE, FALSE, '2026-09-10 09:00:00'),
(10, 5, 1, 'mobile', 'mobile', FALSE, FALSE, '2026-09-07 12:00:00'),
(11, 5, 1, 'web', 'desktop', TRUE, TRUE, '2026-08-22 11:00:00');

INSERT INTO payments VALUES
(1, 1, 'card', 900.00, '2026-08-02 10:05:00'),
(2, 2, 'bank_transfer', 500.00, '2026-08-03 11:05:00'),
(3, 3, 'wallet', 270.00, '2026-08-10 09:05:00'),
(4, 4, 'card', 0.00, '2026-08-15 15:05:00'),
(5, 5, 'wallet', 400.00, '2026-08-20 16:05:00'),
(6, 7, 'bank_transfer', 630.00, '2026-09-01 08:05:00'),
(7, 8, 'card', 250.00, '2026-07-31 23:05:00'),
(8, 9, 'wallet', 300.00, '2026-09-05 14:05:00'),
(9, 10, 'card', 150.00, '2026-09-10 10:05:00');

INSERT INTO dim_items VALUES
(1, 101, 'Sản phẩm A cơ bản', 5, 10, TRUE, TRUE, 1, 1, 1),
(2, 102, 'Sản phẩm B tiêu chuẩn', 50, 5, TRUE, TRUE, 1, 1, 1),
(3, 103, 'Sản phẩm C gia đình', 8, 8, TRUE, TRUE, 2, 2, 2),
(4, 104, 'Sản phẩm D thời trang', 30, 10, TRUE, TRUE, 3, 2, 1),
(5, 105, 'Sản phẩm test nội bộ', 0, 5, FALSE, FALSE, 4, 3, 1),
(6, 101, 'Sản phẩm A bản giới hạn', 6, 3, TRUE, TRUE, 1, 3, 2);
