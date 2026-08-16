"""Comprehensive Seed Data Generator for Golden Retail Benchmark Database.

Populates 100% of ALL 36 TABLES in golden_retail_schema with realistic, high-volume data:
  - 10 Timezones, 10 Countries, 20 Regions, 30 Cities
  - 5 Languages, 5 Currencies, 8 UOMs
  - 50 Employees, 300 Login Histories
  - 10 Stores & Store Settings
  - 25 Item Categories, 20 Suppliers, Supplier Taxes & Item Taxes
  - 200 Products, 200 Barcodes, 400 Price Records
  - 1,000 Customers, 1,000 Loyalty Cards
  - 15 Discount Types, 60 Category/Item Discount Mappings
  - 60 Payment Terms (Matrix of Channel, Delivery, Method, Time)
  - 5,000 Orders (Order_Header), 15,000+ Order Lines (Order_Line), 10,000 Status Logs
  - 8,000 Web Sessions (Web_Session), 6,000 Carts (Cart)
"""

import os
import random
import sys
from datetime import datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Output file path
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
OUTPUT_SQL_PATH = os.path.join(OUTPUT_DIR, "golden_retail_seed.sql")

# Extensive Datasets for Realism
HO_LIST = [
    "Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Vũ", "Võ", "Đặng", 
    "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý", "Phan", "Đinh", "Trịnh", "Lương", "Cao"
]

DEM_LIST = [
    "Văn", "Thị", "Minh", "Quang", "Đức", "Hoàng", "Thanh", "Ngọc", "Anh", 
    "Tuấn", "Hữu", "Khánh", "Đình", "Phương", "Hải", "Gia", "Bảo", "Xuân", "Mỹ", "Trọng"
]

TEN_LIST = [
    "An", "Bình", "Cường", "Dũng", "Em", "Phúc", "Giang", "Hà", "Hùng", 
    "Hải", "Khanh", "Linh", "Nam", "Oanh", "Phong", "Quân", "Sơn", "Trang", 
    "Tùng", "Vinh", "Đạt", "Huy", "Khang", "Nhi", "Nhung", "Thảo", "Vy",
    "Thành", "Nghĩa", "Nhật", "Hằng", "Nga", "Yến", "Quyên", "Tâm", "Đức", "Tân"
]

STREETS = [
    "Lê Lợi", "Nguyễn Huệ", "Trần Hưng Đạo", "Hai Bà Trưng", "Cầu Giấy", 
    "Nguyễn Trãi", "Điện Biên Phủ", "Lê Duẩn", "Xã Đàn", "Hùng Vương",
    "Hoàng Hoa Thám", "Lý Tự Trọng", "Nguyễn Thị Minh Khai", "Cách Mạng Tháng 8",
    "Trần Phú", "Bạch Đằng", "Nguyễn Văn Linh", "Phạm Văn Đồng", "Võ Văn Kiệt", "Kim Mã"
]


def generate_header() -> str:
    """Generate SQL header statements."""
    return (
        "-- ==============================================================================\n"
        "-- GOLDEN RETAIL BENCHMARK MASSIVE SEED DATA DUMP\n"
        f"-- Generated At: {datetime.now().isoformat()}\n"
        "-- Engine: MySQL / MariaDB / PostgreSQL Compatible DML\n"
        "-- Covers: ALL 36 TABLES (1,000 Customers, 200 Products, 5,000 Orders, 15,000+ Lines)\n"
        "-- ==============================================================================\n\n"
        "SET FOREIGN_KEY_CHECKS = 0;\n\n"
    )


def generate_footer() -> str:
    """Generate SQL footer statements."""
    return "\nSET FOREIGN_KEY_CHECKS = 1;\n"


def generate_geography_sql() -> str:
    """Generate geography and timezone lookup data across 30 cities."""
    sql = []
    sql.append("-- ------------------------------------------------------------------------------\n-- MODULE 1: GEOGRAPHY & TIMEZONES\n-- ------------------------------------------------------------------------------")
    
    tz_rows = []
    tz_names = [
        ("Asia/Ho_Chi_Minh", "Múi giờ Vietnam (UTC+7)"),
        ("UTC", "Coordinated Universal Time"),
        ("America/New_York", "Eastern Time (UTC-5)"),
        ("America/Los_Angeles", "Pacific Time (UTC-8)"),
        ("Asia/Tokyo", "Japan Standard Time (UTC+9)"),
        ("Asia/Seoul", "Korea Standard Time (UTC+9)"),
        ("Asia/Singapore", "Singapore Time (UTC+8)"),
        ("Europe/London", "Greenwich Mean Time (UTC+0)"),
        ("Europe/Paris", "Central European Time (UTC+1)"),
        ("Australia/Sydney", "Australian Eastern Time (UTC+10)")
    ]
    for idx, (name, desc) in enumerate(tz_names, start=1):
        tz_rows.append(f"({idx}, '{name}', '{desc}')")
    sql.append("INSERT INTO Time_Zone (ID, Name, Description) VALUES\n" + ",\n".join(tz_rows) + ";")

    countries = ["Việt Nam", "Hoa Kỳ", "Nhật Bản", "Hàn Quốc", "Singapore", "Trung Quốc", "Đức", "Anh", "Pháp", "Úc"]
    c_rows = [f"({idx}, '{name}')" for idx, name in enumerate(countries, start=1)]
    sql.append("INSERT INTO Country (ID, Name) VALUES\n" + ",\n".join(c_rows) + ";")

    regions = [
        ("Miền Bắc", 1), ("Miền Trung", 1), ("Miền Nam", 1),
        ("California", 2), ("New York", 2), ("Texas", 2),
        ("Kanto", 3), ("Kansai", 3), ("Seoul Capital", 4), ("Gyeonggi", 4),
        ("Central Region", 5), ("Guangdong", 6), ("Bavaria", 7), ("Greater London", 8),
        ("Île-de-France", 9), ("New South Wales", 10), ("Miền Tây", 1), ("Tây Nguyên", 1),
        ("Đông Nam Bộ", 1), ("Hồng Hà", 1)
    ]
    r_rows = [f"({idx}, '{name}', {cid})" for idx, (name, cid) in enumerate(regions, start=1)]
    sql.append("INSERT INTO Region (ID, Name, Country_ID) VALUES\n" + ",\n".join(r_rows) + ";")

    cities = [
        ("Hà Nội", 1, 1, 100000), ("Hải Phòng", 1, 1, 180000), ("Quảng Ninh", 1, 1, 200000),
        ("Bắc Ninh", 1, 1, 220000), ("Thái Nguyên", 1, 1, 250000), ("Đà Nẵng", 2, 1, 550000),
        ("Huế", 2, 1, 530000), ("Nha Trang", 2, 1, 650000), ("Quy Nhơn", 2, 1, 590000),
        ("Thanh Hóa", 2, 1, 440000), ("TP. Hồ Chí Minh", 3, 1, 700000), ("Cần Thơ", 17, 1, 900000),
        ("Bình Dương", 19, 1, 820000), ("Đồng Nai", 19, 1, 810000), ("Vũng Tàu", 19, 1, 780000),
        ("Đà Lạt", 18, 1, 670000), ("Buôn Ma Thuột", 18, 1, 630000), ("Phú Quốc", 17, 1, 920000),
        ("Rạch Giá", 17, 1, 910000), ("Long Xuyên", 17, 1, 880000), ("Los Angeles", 4, 4, 90001),
        ("San Francisco", 4, 4, 94101), ("New York City", 5, 3, 10001), ("Houston", 6, 3, 77001),
        ("Tokyo", 7, 5, 1000001), ("Osaka", 8, 5, 5300001), ("Seoul", 9, 6, 10000),
        ("Singapore", 11, 7, 188065), ("Munich", 13, 9, 80331), ("London", 14, 8, 100000)
    ]
    city_rows = [f"({idx}, '{name}', {rid}, {tzid}, {zipc})" for idx, (name, rid, tzid, zipc) in enumerate(cities, start=1)]
    sql.append("INSERT INTO City (ID, Name, Region_ID, Time_Zone_ID, Zip_Code) VALUES\n" + ",\n".join(city_rows) + ";")

    return "\n".join(sql) + "\n\n"


def generate_lookups_sql() -> str:
    """Generate system lookup definitions."""
    sql = []
    sql.append("-- ------------------------------------------------------------------------------\n-- MODULE 2: SYSTEM LOOKUPS & STORE SETTINGS\n-- ------------------------------------------------------------------------------")
    sql.append("INSERT INTO Language (ID, Name, Short_Name, Description) VALUES "
               "(1, 'Tiếng Việt', 'vi', 'Ngôn ngữ hiển thị chính'), "
               "(2, 'English', 'en', 'English International'), "
               "(3, 'Japanese', 'ja', 'Japanese Language'), "
               "(4, 'Korean', 'ko', 'Korean Language'), "
               "(5, 'Chinese', 'zh', 'Chinese Language');")
    sql.append("INSERT INTO Currency (ID, Name, Short_Name, Symbol, Description) VALUES "
               "(1, 'Việt Nam Đồng', 'VND', '₫', 'Đơn vị tiền tệ Việt Nam'), "
               "(2, 'US Dollar', 'USD', '$', 'Đô la Mỹ'), "
               "(3, 'Euro', 'EUR', '€', 'Đồng Tiền Chung Châu Âu'), "
               "(4, 'Japanese Yen', 'JPY', '¥', 'Yên Nhật'), "
               "(5, 'Korean Won', 'KRW', '₩', 'Won Hàn Quốc');")
    sql.append("INSERT INTO Unit_Of_Measure (ID, Name, Symbol, Description) VALUES "
               "(1, 'Cái', 'Pcs', 'Đơn vị sản phẩm rời'), "
               "(2, 'Hộp', 'Box', 'Đóng gói theo hộp'), "
               "(3, 'Bộ', 'Set', 'Bộ sản phẩm nguyên cụm'), "
               "(4, 'Kg', 'Kg', 'Kilogram khối lượng'), "
               "(5, 'Gói', 'Pack', 'Gói sản phẩm'), "
               "(6, 'Chai', 'Btl', 'Chai lọ đóng dung dịch'), "
               "(7, 'Cuộn', 'Roll', 'Cuộn vật liệu'), "
               "(8, 'Thùng', 'Carton', 'Thùng đóng kiện');")
    return "\n".join(sql) + "\n\n"


def generate_employees_sql(count: int = 50) -> str:
    """Generate 50 employees, 6 roles, and 300 employee login histories."""
    sql = []
    sql.append("-- ------------------------------------------------------------------------------\n-- MODULE 3: EMPLOYEES & ROLES\n-- ------------------------------------------------------------------------------")
    sql.append("INSERT INTO Employee_Role (ID, Name, Description, Is_Active) VALUES "
               "(1, 'Admin', 'Quản trị toàn bộ hệ thống', '1'), "
               "(2, 'Store Manager', 'Quản lý vận hành cửa hàng', '1'), "
               "(3, 'Sales Staff', 'Nhân viên bán hàng POS/Online', '1'), "
               "(4, 'Warehouse Staff', 'Nhân viên quản lý kho', '1'), "
               "(5, 'Customer Care', 'Nhân viên hỗ trợ CSKH', '1'), "
               "(6, 'Finance Accountant', 'Kế toán tài chính', '1');")

    emp_rows = []
    for i in range(1, count + 1):
        ho = HO_LIST[(i - 1) % len(HO_LIST)]
        dem = DEM_LIST[(i - 1) % len(DEM_LIST)]
        ten = TEN_LIST[(i - 1) % len(TEN_LIST)]
        role_id = 1 if i == 1 else (2 if i <= 10 else (3 if i <= 35 else (4 if i <= 45 else (5 if i <= 48 else 6))))
        emp_rows.append(f"({i}, {role_id}, 'EMP-{i:05d}', '{ho} {dem}', '{ten}', 'emp{i}@goldenretail.vn', '0901234{i:03d}', '1')")
    sql.append("INSERT INTO Employee (ID, Employee_Role_ID, Code, First_Name, Last_Name, Email, Phone, Is_Active) VALUES\n" + ",\n".join(emp_rows) + ";")

    login_rows = []
    for i in range(1, 301):
        emp_id = (i % count) + 1
        role_id = 1 if emp_id == 1 else (2 if emp_id <= 10 else 3)
        day = (i % 28) + 1
        hour_start = (8 + (i % 10)) % 24
        hour_end = (hour_start + 8) % 24
        login_rows.append(f"({i}, {emp_id}, {role_id}, '2026-01-{day:02d} {hour_start:02d}:00:00', '2026-01-{day:02d} {hour_end:02d}:00:00', '192.168.1.{10+(i%200)}', 'Đăng nhập hệ thống')")
    sql.append("INSERT INTO Employee_Login (ID, Employee_ID, Employee_Role_ID, Login_Time, Logout_Time, Device_IP, Comments) VALUES\n" + ",\n".join(login_rows) + ";")


    return "\n".join(sql) + "\n\n"


def generate_stores_sql() -> str:
    """Generate 10 stores and 10 store settings."""
    sql = []
    store_names = [
        ("STR-HN01", "Golden Retail Hà Nội Flagship", 1, 1, "123 Cầu Giấy, Hà Nội"),
        ("STR-HCM01", "Golden Retail TP.HCM Quận 1", 11, 2, "456 Nguyễn Huệ, Quận 1, TP.HCM"),
        ("STR-DN01", "Golden Retail Đà Nẵng Central", 6, 3, "789 Lê Duẩn, Đà Nẵng"),
        ("STR-CT01", "Golden Retail Cần Thơ Plaza", 12, 4, "12 Hòa Bình, Cần Thơ"),
        ("STR-HP01", "Golden Retail Hải Phòng City", 2, 5, "55 Lạch Tray, Hải Phòng"),
        ("STR-NT01", "Golden Retail Nha Trang Beach", 8, 6, "88 Trần Phú, Nha Trang"),
        ("STR-HUE01", "Golden Retail Huế Citadel", 7, 7, "22 Hùng Vương, Huế"),
        ("STR-VT01", "Golden Retail Vũng Tàu Sea", 15, 8, "99 Thùy Vân, Vũng Tàu"),
        ("STR-ECOMM", "Golden E-Commerce Online Store", 11, 1, "Kênh Online Quốc tế"),
        ("STR-APP01", "Golden Mobile App Store", 11, 1, "Ứng Dụng Di Động AppStore/PlayStore")
    ]

    s_rows = []
    st_rows = []
    for idx, (code, name, city_id, admin_id, addr) in enumerate(store_names, start=1):
        s_rows.append(
            f"({idx}, {city_id}, 1, 1, {admin_id}, '{code}', '{name}', '1', 'Công ty Cổ phần Bán lẻ Golden Việt Nam', "
            f"'0101234567-{idx:03d}', '{addr}', 'REG-{idx:03d}', '21.0285,105.8542', '100000', '0243999{idx:04d}', NULL, "
            f"'store{idx}@goldenretail.vn', 'https://goldenretail.vn', NULL, 'Vietcombank HQ', 'VCB', '001100{idx:07d}', 'Chi nhánh cửa hàng #{idx}')"
        )
        st_rows.append(
            f"({idx}, {idx}, 1, 1, 1, '1', '0', '1', '0', '1', '1', 30, 2, '1', '2026-01-01 00:00:00', '2026-01-01 00:00:00', NULL, '1', 'Cấu hình chuẩn cửa hàng #{idx}')"
        )

    sql.append("INSERT INTO Store (ID, City_ID, Language_ID, Currency_ID, Admin_User_ID, Code, Name, Is_Active, Legal_Entity_Name, Tax_Code, Address, Registration_Number, GPS_Location, Postal_Code, Phone, Fax, Email, Website, Logo, Bank_Branch, Bank_Code, Bank_Account, Comments) VALUES\n" + ",\n".join(s_rows) + ";")
    sql.append("INSERT INTO Setting (ID, Store_ID, Default_Payment_Method_ID, Default_Tax_Type_ID, Default_Quantity, In_Stock_Check, Negative_Stock_Allowed, Price_Includes_Tax, Negative_Price_Allowed, Moving_Average_Price, Discount_Before_Tax, Default_Due_Days, Decimal_Places, Public_Reviews_Allowed, Created_Time, Start_Time, End_Time, Is_Active, Comments) VALUES\n" + ",\n".join(st_rows) + ";")

    return "\n".join(sql) + "\n\n"


def generate_categories_suppliers_and_taxes() -> str:
    """Generate 25 Categories, 20 Suppliers, Supplier Tax Types, Supplier Item Taxes."""
    sql = []
    sql.append("-- ------------------------------------------------------------------------------\n-- MODULE 4: PRODUCTS, SUPPLIERS & TAXES\n-- ------------------------------------------------------------------------------")
    
    cats = [
        (1, None, 'Điện thoại & Tablet', 'Thiết bị di động thông minh'),
        (2, 1, 'Smartphone', 'Điện thoại thông minh'),
        (3, 1, 'Tablet', 'Máy tính bảng'),
        (4, None, 'Laptop & Máy tính', 'Máy tính xách tay & Phụ kiện'),
        (5, 4, 'Laptop Văn phòng', 'Laptop mỏng nhẹ văn phòng'),
        (6, 4, 'Laptop Gaming', 'Laptop cấu hình cao chơi game'),
        (7, None, 'Thời trang & Phụ kiện', 'Quần áo thời trang nam nữ'),
        (8, 7, 'Áo Nam', 'Áo sơ mi, áo polo nam'),
        (9, 7, 'Giày Sneaker', 'Giày thể thao cao cấp'),
        (10, None, 'Gia dụng & Đời sống', 'Thiết bị gia dụng gia đình'),
        (11, 10, 'Nồi cơm & Bếp từ', 'Thiết bị nhà bếp'),
        (12, 10, 'Quạt & Máy làm mát', 'Thiết bị làm mát không khí'),
        (13, None, 'Âm thanh & Phụ kiện Số', 'Tai nghe, loa bluetooth, sạc'),
        (14, 13, 'Tai nghe Wireless', 'Tai nghe chống ồn không dây'),
        (15, 13, 'Loa Bluetooth', 'Loa di động âm thanh sống động'),
        (16, 7, 'Quần Nam', 'Quần tây, quần jeans nam'),
        (17, 7, 'Thời trang Nữ', 'Váy đầm, áo nữ thời trang'),
        (18, 4, 'Màn hình Máy tính', 'Màn hình đồ họa & gaming'),
        (19, 4, 'Bàn phím & Chuột', 'Phụ kiện máy tính văn phòng'),
        (20, 10, 'Tủ lạnh & Máy giặt', 'Thiết bị điện lạnh gia đình'),
        (21, 1, 'Đồng hồ Thông minh', 'Smartwatch & Vòng đeo tay'),
        (22, 13, 'Sạc & Cáp kết nối', 'Củ sạc nhanh & cáp sạc'),
        (23, 10, 'Robot Hút bụi', 'Thiết bị lau dọn thông minh'),
        (24, 7, 'Balo & Túi xách', 'Balo đựng laptop & túi xách'),
        (25, None, 'Thực phẩm & Đồ uống', 'Bánh kẹo thực phẩm đóng gói')
    ]
    c_rows = [f"({cid}, {pid if pid else 'NULL'}, '{name}', '{desc}', '1', NULL)" for cid, pid, name, desc in cats]
    sql.append("INSERT INTO Item_Category (ID, Parent_Category_ID, Name, Description, Is_Active, Comments) VALUES\n" + ",\n".join(c_rows) + ";")

    suppliers = [
        ("Apple Việt Nam", 1, 1), ("Samsung Electronics", 2, 11), ("Asus Technology", 1, 1), ("May An Phước", 2, 11),
        ("Sunhouse Group", 1, 1), ("Sony Việt Nam", 2, 11), ("LG Electronics", 1, 1), ("Xiaomi Việt Nam", 2, 11),
        ("Logitech Asia", 1, 1), ("Anker Innovations", 2, 11), ("Dell Global", 1, 1), ("HP Inc Việt Nam", 2, 11),
        ("Lenovo Technology", 1, 1), ("Bitis Việt Nam", 2, 11), ("Việt Tiến Garment", 1, 1), ("Panasonic Việt Nam", 2, 11),

        ("Philips Consumer", 1, 1), ("JBL Audio", 2, 11), ("Kingston Tech", 1, 1), ("SanDisk Western Digital", 2, 11)
    ]
    sup_rows = []
    sup_tax_rows = []
    for idx, (name, store_id, city_id) in enumerate(suppliers, start=1):
        sup_rows.append(
            f"({idx}, {store_id}, {city_id}, 'SUP-{idx:03d}', '0243{idx:07d}', 'Đại diện', '{name}', '1', 'Công ty TNHH {name}', "
            f"'010888{idx:04d}', '0', 'Khu Công Nghiệp #{idx}', '100000', 'contact@sup{idx}.vn', 1, '2025-06-01 09:00:00', '1', 'Nhà cung cấp chính thức #{idx}')"
        )
        sup_tax_rows.append(
            f"({idx}, {idx}, 'Thuế NCC {name}', 'STAX-{idx:03d}', 'Thuế giá trị gia tăng NCC', '1', 10.000, '2026-01-01 00:00:00', '2026-01-01 00:00:00', NULL, '1', NULL)"
        )

    sql.append("INSERT INTO Supplier (ID, Store_ID, City_ID, Code, Phone, First_Name, Last_Name, Is_Company, Company_Name, Tax_Number, Is_Tax_Exempted, Billing_Address, Postal_Code, Email, Created_Emp_Login_ID, Created_Time, Is_Active, Comments) VALUES\n" + ",\n".join(sup_rows) + ";")
    sql.append("INSERT INTO Supplier_Tax_Type (ID, Supplier_ID, Name, Code, Description, Is_Percentage, Value, Created_Time, Start_Time, End_Time, Is_Active, Comments) VALUES\n" + ",\n".join(sup_tax_rows) + ";")

    return "\n".join(sql) + "\n\n"


def generate_items_and_prices(count: int = 200) -> str:
    """Generate 200 Products, 200 Barcodes, 400 Price records, and 100 Supplier Item Taxes."""
    sql = []
    prod_names = [
        ("iPhone 15 Pro Max 256GB", 2, 1, 27000000, 32990000),
        ("Samsung Galaxy S24 Ultra 512GB", 2, 2, 25000000, 29990000),
        ("iPad Pro 11 inch M4 Wi-Fi 256GB", 3, 1, 22000000, 26990000),
        ("MacBook Air 13 inch M3 16GB/512GB", 5, 1, 26000000, 30990000),
        ("Asus ROG Strix G16 i9 16GB/1TB", 6, 3, 35000000, 42990000),
        ("Áo Polo Nam An Phước Cao Cấp", 8, 4, 450000, 790000),
        ("Áo Sơ Mi Nam An Phước Dài Tay", 8, 4, 550000, 950000),
        ("Giày Sneaker Thể Thao An Phước", 9, 4, 900000, 1490000),
        ("Nồi Cơm Điện Cao Tần Sunhouse 1.8L", 11, 5, 1200000, 1890000),
        ("Nồi Chiên Không Dầu Sunhouse 6L", 11, 5, 1400000, 2190000),
        ("Tai Nghe Sony WH-1000XM5 Chống Ồn", 14, 6, 6500000, 8490000),
        ("Loa Bluetooth JBL Charge 5", 15, 18, 2800000, 3990000),
        ("Màn Hình Dell UltraSharp 27 inch 4K", 18, 11, 9500000, 12490000),
        ("Bàn Phím Cơ Logitech MX Keys S", 19, 9, 2200000, 2990000),
        ("Chuột Không Dây Logitech MX Master 3S", 19, 9, 1800000, 2490000),
        ("Robot Hút Bụi Xiaomi Vacuum S10", 23, 8, 4500000, 6290000),
        ("Đồng Hồ Apple Watch Series 9 GPS", 21, 1, 7500000, 9990000),
        ("Sạc Nhanh Anker 65W GaNPrime", 22, 10, 600000, 990000),
        ("Tủ Lạnh LG Inverter 315 Lít", 20, 7, 7800000, 10490000),
        ("Balo Laptop Bitis Coolbell 15.6", 24, 14, 350000, 590000)
    ]


    item_rows = []
    barcode_rows = []
    price_rows = []
    sup_item_tax_rows = []
    price_id_counter = 1

    for idx in range(1, count + 1):
        tmpl = prod_names[(idx - 1) % len(prod_names)]
        name_prefix, cat_id, sup_id, cost_base, price_base = tmpl

        sku = f"SKU-PROD{idx:04d}"
        name = (f"{name_prefix} v{idx}" if idx > len(prod_names) else name_prefix)[:50]

        stock = random.randint(30, 400)
        cost = cost_base + random.randint(0, 15) * 10000
        price = price_base + random.randint(0, 15) * 10000
        uom_id = (idx % 8) + 1
        store_id = (idx % 10) + 1

        item_rows.append(
            f"({idx}, {store_id}, {cat_id}, {sup_id}, {uom_id}, '{sku}', '{name}', 'Mô tả chi tiết cho sản phẩm {name}', "
            f"'0', '1', '1', 1, {stock}, {stock+50}, 10, '1', 5, '1', NULL)"
        )
        barcode_rows.append(f"({idx}, {idx}, 'BC-893{idx:010d}', '1', 'Mã vạch chuẩn EAN-13 sản phẩm #{idx}')")

        # Initial price
        tax_val = int(price * 0.1)
        price_before = price - tax_val
        markup = int(((price_before - cost) / cost) * 100)
        price_rows.append(
            f"({price_id_counter}, {idx}, {store_id}, 'Bảng giá áp dụng đợt 1', {cost}, {markup}, {price_before}, {tax_val}, {price}, {price}, '1', '2025-06-01 00:00:00', 1, '2025-06-01 00:00:00', '2026-01-01 00:00:00', '0', NULL)"
        )
        price_id_counter += 1

        # Updated current price
        cost_new = int(cost * 1.05)
        price_new = int(price * 1.05)
        tax_val_new = int(price_new * 0.1)
        price_before_new = price_new - tax_val_new
        markup_new = int(((price_before_new - cost_new) / cost_new) * 100)
        price_rows.append(
            f"({price_id_counter}, {idx}, {store_id}, 'Bảng giá áp dụng hiện tại 2026', {cost_new}, {markup_new}, {price_before_new}, {tax_val_new}, {price_new}, {price_new}, '1', '2026-01-01 00:00:00', 1, '2026-01-01 00:00:00', NULL, '1', NULL)"
        )
        price_id_counter += 1

        if idx <= 100:
            sup_tax_id = ((idx - 1) % 20) + 1
            sup_item_tax_rows.append(f"({idx}, {idx}, {sup_tax_id}, '2026-01-01 00:00:00', '2026-01-01 00:00:00', NULL, 'Thuế sản phẩm từ NCC #{sup_tax_id}')")

    sql.append("INSERT INTO Item (ID, Store_ID, Item_Category_ID, Supplier_ID, Unit_Of_Measure_ID, SKU_Code, Name, Description, Is_Service, In_Stock, Using_Default_Quantity, Default_Quantity, Current_Stock_Quantity, Preferred_Stock_Quantity, Min_Stock_Quantity, Low_Stock_Warning, Low_Stock_Quantity, Is_Active, Comments) VALUES\n" + ",\n".join(item_rows) + ";")
    sql.append("INSERT INTO Bar_Code (ID, Item_ID, Bar_Code, Is_Active, Description) VALUES\n" + ",\n".join(barcode_rows) + ";")
    sql.append("INSERT INTO Price (ID, Item_ID, Store_ID, Description, Current_Item_Cost, Markup_percentage, Price_Before_Tax, Tax_Value, Price_After_Tax, Sale_Price, Price_Change_Allowed, Created_Time, Created_Emp_Login_ID, Start_Time, End_Time, Is_Active, Comments) VALUES\n" + ",\n".join(price_rows) + ";")
    sql.append("INSERT INTO Supplier_Item_Tax_Type (ID, Item_ID, Supplier_Tax_Type_ID, Created_Time, Start_Time, End_Time, Description) VALUES\n" + ",\n".join(sup_item_tax_rows) + ";")

    return "\n".join(sql) + "\n\n"


def generate_customers_sql(count: int = 1000) -> str:
    """Generate 1,000 customers and 1,000 loyalty cards."""
    sql = []
    sql.append("-- ------------------------------------------------------------------------------\n-- MODULE 5: CUSTOMERS & LOYALTY\n-- ------------------------------------------------------------------------------")
    sql.append("INSERT INTO Loyalty_Card_Type (ID, Name, Description, Discount_Percentage, Min_Accumulated_Points, Is_Active) VALUES "
               "(1, 'Bronze Member', 'Hạng thẻ Đồng', 0.00, 0, '1'), "
               "(2, 'Silver Member', 'Hạng thẻ Bạc', 3.00, 100, '1'), "
               "(3, 'Gold Member', 'Hạng thẻ Vàng', 5.00, 500, '1'), "
               "(4, 'VIP Member', 'Hạng thẻ Kim Cương VIP', 10.00, 1000, '1');")

    cust_rows = []
    loyalty_rows = []

    for i in range(1, count + 1):
        ho = HO_LIST[i % len(HO_LIST)]
        dem = DEM_LIST[(i * 3) % len(DEM_LIST)]
        ten = TEN_LIST[(i * 7) % len(TEN_LIST)]
        phone = f"098{i:07d}" if i < 10000000 else f"091{i:07d}"
        email = f"customer{i}@gmail.com"
        username = f"user_{i:05d}"
        city_id = (i % 30) + 1
        store_id = (i % 10) + 1
        street = STREETS[i % len(STREETS)]
        address = f"Số {i * 5} đường {street}"
        
        cust_rows.append(
            f"({i}, {city_id}, 'CUST-{i:05d}', '{phone}', '{ho} {dem}', '{ten}', '0', NULL, NULL, '0', "
            f"'{address}', '700000', '1', '{email}', '{username}', 'hashed_password_hash', 0.00, 1, {store_id}, "
            f"'2025-06-01 10:00:00', '2026-02-01 15:30:00', '1', 'Khách hàng thành viên #{i}')"
        )

        card_type = 1 if i <= 500 else (2 if i <= 800 else (3 if i <= 950 else 4))
        points = (i * 18) % 2000
        loyalty_rows.append(f"({i}, {i}, {card_type}, 'LOYAL-{i:06d}', {points}, '2025-06-01 10:00:00', '1')")

    sql.append("INSERT INTO Customer (ID, City_ID, Code, Phone, First_Name, Last_Name, Is_Company, Company_Name, Tax_Number, Is_Tax_Exempted, Billing_Address, Postal_Code, Is_Registered_Online, Email, Username, Password, Credit, Created_Emp_Login_ID, Created_At_Store_ID, Created_Time, Last_Login_Time, Is_Active, Comments) VALUES\n" + ",\n".join(cust_rows) + ";")
    sql.append("INSERT INTO Loyalty_Card (ID, Customer_ID, Loyalty_Card_Type_ID, Card_Number, Total_Points, Issue_Date, Is_Active) VALUES\n" + ",\n".join(loyalty_rows) + ";")

    return "\n".join(sql) + "\n\n"


def generate_discounts_taxes_and_terms() -> str:
    """Generate Tax Types, Discount Types, Discounts, Sales Channels, Delivery, Payment Methods & Terms."""
    sql = []
    sql.append("-- ------------------------------------------------------------------------------\n-- MODULE 6 & 7: DISCOUNTS, TAXES, CHANNELS & PAYMENT TERMS\n-- ------------------------------------------------------------------------------")
    
    tax_types = [
        ("Thuế VAT 10%", "VAT10", 10.000), ("Thuế VAT 8%", "VAT8", 8.000),
        ("Thuế Tiêu Thụ Đặc Biệt", "SCT", 15.000), ("Thuế Nhập Khẩu", "IMPORT", 5.000),
        ("Thuế Môi Trường", "ENV", 2.000), ("Thuế Miễn Phí", "ZERO", 0.000)
    ]
    tt_rows = []
    for idx, (name, code, val) in enumerate(tax_types, start=1):
        tt_rows.append(f"({idx}, 1, '{name}', '{code}', 'Mô tả loại thuế {name}', '1', {val}, '2026-01-01 00:00:00', '2026-01-01 00:00:00', NULL, '1', NULL)")
    sql.append("INSERT INTO Tax_Type (ID, Store_ID, Name, Code, Description, Is_Percentage, Value, Created_Time, Start_Time, End_Time, Is_Active, Comments) VALUES\n" + ",\n".join(tt_rows) + ";")

    discount_types = [
        ("Khuyến Mãi Tết 2026", "TET2026", 10.000), ("Ưu Đãi VIP Khách Hàng", "VIPDISCOUNT", 5.000),
        ("Black Friday Sale", "BLACKFRIDAY", 20.000), ("Flash Sale 11.11", "FLASHSALE11", 15.000),
        ("Voucher Khách Hàng Mới", "WELCOME100", 10.000), ("Khuyến Mãi Mùa Hè", "SUMMERSALE", 8.000),
        ("Giảm Giá Phụ Kiện", "ACCES20", 20.000), ("Giảm Giá Sinh Nhật", "HAPPYBDAY", 12.000),
        ("Khuyến Mãi Cuối Tuần", "WEEKEND5", 5.000), ("Voucher Shopee Live", "SHOPEELIVE", 15.000),
        ("Ưu Đãi Thanh Toán MoMo", "MOMO50K", 5.000), ("Khuyến Mãi Lễ Quốc Khánh", "SEPT2", 10.000),
        ("Giảm Giá Mua Sỉ", "BULKBUY", 18.000), ("Voucher 8/3 Thời Trang", "WOMEN83", 10.000),
        ("Clearance Sale Xả Kho", "CLEARANCE", 30.000)
    ]
    dt_rows = []
    disc_map_rows = []
    for idx, (name, code, val) in enumerate(discount_types, start=1):
        dt_rows.append(
            f"({idx}, 1, '{name}', 'Chương trình {name}', '1', {val}, '2026-01-01 00:00:00', '2026-01-01 00:00:00', NULL, "
            f"NULL, '{code}', 500000.000, 1, '1', '0', 1000000.000, '1', 'Ghi chú chương trình #{idx}')"
        )

    # 60 Category & Item Discount Mappings
    for idx in range(1, 61):
        dt_id = ((idx - 1) % 15) + 1
        cat_id = ((idx - 1) % 25) + 1
        item_id = ((idx - 1) % 200) + 1
        disc_map_rows.append(f"({idx}, {dt_id}, {cat_id}, {item_id}, 'Quy định chiết khấu #{idx}', 'Khuyến mãi theo mặt hàng & danh mục')")

    sql.append("INSERT INTO Discount_Type (ID, Store_ID, Name, Description, Is_Percentage, Value, Created_Time, Start_Time, End_Time, Loyalty_Card_Type_ID, Coupon_Code, Min_Order_Value, Min_Item_Quantity, Apply_To_All, Apply_To_Next, Max_Discount_Value, Is_Active, Comments) VALUES\n" + ",\n".join(dt_rows) + ";")
    sql.append("INSERT INTO Discount (ID, Discount_Type_ID, Item_Category_ID, Item_ID, Description, Comments) VALUES\n" + ",\n".join(disc_map_rows) + ";")

    sql.append("INSERT INTO Sales_Channel (ID, Name, Description, Is_Active) VALUES "
               "(1, 'POS Store Direct', 'Bán hàng trực tiếp tại Cửa hàng', '1'), "
               "(2, 'Website E-Commerce', 'Bán hàng trực tuyến qua Website', '1'), "
               "(3, 'Mobile App', 'Bán hàng qua ứng dụng di động', '1'), "
               "(4, 'Shopee Marketplace', 'Kênh sàn TMĐT Shopee', '1'), "
               "(5, 'Lazada Marketplace', 'Kênh sàn TMĐT Lazada', '1');")

    sql.append("INSERT INTO Delivery_Type (ID, Name, Description, Is_Active) VALUES "
               "(1, 'In-Store Pickup', 'Nhận hàng trực tiếp tại cửa hàng', '1'), "
               "(2, 'Express Delivery', 'Giao hàng hỏa tốc trong 2h', '1'), "
               "(3, 'Standard Shipping', 'Giao hàng tiêu chuẩn toàn quốc', '1'), "
               "(4, 'GrabExpress / Ahamove', 'Giao hàng siêu tốc nội thành', '1');")

    sql.append("INSERT INTO Payment_Method (ID, Name, Code, Sequence_No, Is_Active, Is_Customer_Required, Description) VALUES "
               "(1, 'Tiền mặt', 'CASH', 1, '1', '0', 'Thanh toán tiền mặt'), "
               "(2, 'Chuyển khoản Ngân hàng', 'BANK_TRANSFER', 2, '1', '1', 'Chuyển khoản QR Code Bank'), "
               "(3, 'Thẻ Tín dụng / Ghi nợ', 'CREDIT_CARD', 3, '1', '1', 'Thanh toán thẻ POS/Online'), "
               "(4, 'Ví MoMo', 'MOMO', 4, '1', '1', 'Thanh toán ví MoMo'), "
               "(5, 'Ví ZaloPay', 'ZALOPAY', 5, '1', '1', 'Thanh toán ví ZaloPay'), "
               "(6, 'Thanh toán khi nhận hàng', 'COD', 6, '1', '1', 'COD ship hàng');")

    sql.append("INSERT INTO Payment_Time (ID, Name, Description, Is_Active) VALUES "
               "(1, 'Trả ngay', 'Thanh toán ngay khi chốt đơn', '1'), "
               "(2, 'Trả khi nhận hàng', 'Thanh toán COD', '1'), "
               "(3, 'Công nợ 30 ngày', 'Bán hàng công nợ trả sau', '1');")

    # 60 Payment Terms Matrix
    p_terms = []
    p_term_counter = 1
    for chan in range(1, 6):
        for deliv in range(1, 5):
            for pmethod in range(1, 4):
                p_terms.append(f"({p_term_counter}, {chan}, {deliv}, {pmethod}, 1, '1', '1', 'Điều khoản thanh toán kết hợp #{p_term_counter}')")
                p_term_counter += 1
                if p_term_counter > 60:
                    break
            if p_term_counter > 60:
                break
        if p_term_counter > 60:
            break

    sql.append("INSERT INTO Payment_Term (ID, Sales_Channel_ID, Delivery_Type_ID, Payment_Method_ID, Payment_Time_ID, Is_Allowed, Is_Active, Comments) VALUES\n" + ",\n".join(p_terms) + ";")

    sql.append("INSERT INTO Order_Status (ID, Name, Description, Is_Active) VALUES "
               "(1, 'Pending', 'Đơn hàng mới chờ xác nhận', '1'), "
               "(2, 'Approved', 'Đã xác nhận đơn hàng', '1'), "
               "(3, 'Processing', 'Đang đóng gói sản phẩm', '1'), "
               "(4, 'Delivered', 'Đã giao cho đơn vị vận chuyển', '1'), "
               "(5, 'Completed', 'Đã giao thành công & Hoàn tất', '1'), "
               "(6, 'Canceled', 'Đơn hàng đã hủy', '1');")

    return "\n".join(sql) + "\n\n"


def generate_orders_and_analytics(num_orders: int = 5000, num_customers: int = 1000, num_products: int = 200) -> str:
    """Generate 5,000 order headers, 15,000+ order lines, and 10,000 status history records."""
    sql = []
    sql.append("-- ------------------------------------------------------------------------------\n-- MODULE 8 & 9: ORDERS, TRANSACTIONS, WEB SESSIONS & CARTS\n-- ------------------------------------------------------------------------------")

    order_headers = []
    order_lines = []
    status_histories = []

    statuses = ["Completed", "Completed", "Completed", "Completed", "Completed", "Delivered", "Delivered", "Canceled"]
    line_counter = 1
    hist_counter = 1

    for order_id in range(1, num_orders + 1):
        cust_id = random.randint(1, num_customers)
        store_id = random.randint(1, 10)
        channel_id = random.randint(1, 5)
        delivery_id = random.randint(1, 4)
        payment_method_id = random.randint(1, 6)
        payment_time_id = 1 if payment_method_id != 6 else 2

        order_no = f"ORD-2026{order_id:06d}"
        days_ago = random.randint(1, 180)
        created_dt = datetime.now() - timedelta(days=days_ago, hours=random.randint(0, 23), minutes=random.randint(0, 59))
        created_str = created_dt.strftime("%Y-%m-%d %H:%M:%S")

        status = random.choice(statuses)
        is_test = '1' if order_id % 75 == 0 else '0'  # ~65 test orders for filtering check
        seq = (order_id % 7) + 1
        is_completed = '1' if status == "Completed" else '0'
        is_canceled = '1' if status == "Canceled" else '0'
        canceled_time_val = f"'{created_str}'" if is_canceled == '1' else "NULL"
        cancel_reason_val = "'Khách hàng đổi ý / Hủy đơn'" if is_canceled == '1' else "NULL"

        num_items = random.randint(1, 5)
        order_gross = 0
        order_tax = 0
        order_discount = 0

        for l_idx in range(1, num_items + 1):
            item_id = random.randint(1, num_products)
            qty = random.randint(1, 3)
            unit_cost = 200000 + (item_id * 50000)
            unit_price = int(unit_cost * 1.35)
            gross = unit_price * qty
            tax = int(gross * 0.1)
            disc = int(gross * 0.05) if random.random() > 0.65 else 0
            net = gross + tax - disc

            order_gross += gross
            order_tax += tax
            order_discount += disc

            order_lines.append(
                f"({line_counter}, {store_id}, {order_id}, {item_id}, 'LINE-{l_idx}', 'Mặt hàng mua mã #{item_id}', "
                f"NULL, {qty}, {unit_cost}, 35, {gross - tax}, {tax}, {gross}, {gross}, {disc}, {net}, 0.00, NULL, {net}, "
                f"'{is_canceled}', {canceled_time_val}, {cancel_reason_val}, '0', NULL, NULL, 'Sản phẩm đóng gói đẹp, giao hàng đúng hẹn!', '1', NULL)"
            )
            line_counter += 1

        total_price = order_gross + order_tax - order_discount

        order_headers.append(
            f"({order_id}, {store_id}, {channel_id}, {delivery_id}, {payment_method_id}, {payment_time_id}, '{order_no}', "
            f"{cust_id}, {cust_id}, 1, {cust_id}, '{created_str}', 1, 1, 'Giao hàng giờ hành chính', "
            f"{order_gross - order_tax}, {order_tax}, {order_gross}, {order_gross}, 0.00, {order_discount}, {order_discount}, "
            f"0.00, {total_price}, 0.00, NULL, {total_price}, '{status}', '{created_str}', '{is_test}', {seq}, "
            f"'1', '{created_str}', '1', '{created_str}', '{is_canceled}', NULL, NULL, '0', NULL, '1', '{created_str}', "
            f"'1', '{created_str}', '1', '{created_str}', '{is_completed}', '{created_str}', '0', NULL, 'Đơn hàng mua sắm thực tế')"
        )

        status_histories.append(f"({hist_counter}, {order_id}, 1, '{created_str}', NULL)")
        hist_counter += 1
        if is_completed == '1':
            status_histories.append(f"({hist_counter}, {order_id}, 5, '{created_str}', NULL)")
            hist_counter += 1

    sql.append("INSERT INTO Order_Header (ID, Store_ID, Sales_Channel_ID, Delivery_Type_ID, Payment_Method_ID, Payment_Time_ID, Order_No, Customer_ID, Loyalty_Card_ID, Created_Emp_Login_ID, Created_Customer_ID, Created_Time, Approved_Emp_Login_ID, Managed_Emp_Login_ID, Customer_Notes, Price_Before_Tax, Total_Tax_Value, Price_After_Tax, Price_Before_Discount, Order_Items_Discount, Order_Discount, Total_Discount_Value, Return_Amount, Price_After_Discount, Price_Adjustment, Price_Adjustment_Reason, Price, Latest_Status, Latest_Status_Update, Is_Test_Order, Customer_Order_Seq, Is_Submitted, Submitted_Time, Is_Approved, Approved_Time, Is_Canceled, Canceled_Time, Cancel_Reason, Is_Scheduled, Scheduled_Time, Is_Ready, Ready_Time, Is_Delivered, Delivered_Time, Is_Paid, Payment_Time, Is_Completed, Completed_Time, Return_Required, Return_Time, Comments) VALUES\n" + ",\n".join(order_headers) + ";")
    sql.append("INSERT INTO Order_Line (ID, Store_ID, Order_ID, Item_ID, Line_No, Description, Customer_Notes, Quantity, Current_Item_Cost, Markup_Percentage, Price_Before_Tax, Tax_Value, Price_After_Tax, Price_Before_Discount, Discount_Value, Price_After_Discount, Price_Adjustment, Price_Adjustment_Reason, Price, Is_Canceled, Canceled_Time, Cancel_Reason, Return_Required, Return_Quantity, Return_Time, Customer_Review, Customer_Like, Comments) VALUES\n" + ",\n".join(order_lines) + ";")
    sql.append("INSERT INTO Order_Status_History (ID, Order_ID, Order_Status_ID, Start_Time, End_Time) VALUES\n" + ",\n".join(status_histories) + ";")

    return "\n".join(sql) + "\n\n"


def generate_web_sessions_and_carts(num_sessions: int = 8000, num_orders: int = 5000, num_customers: int = 1000) -> str:
    """Generate 8,000 web sessions and 6,000 carts including converted and non-converted traffic."""
    sql = []
    web_sessions = []
    carts = []

    utm_sources = ["google", "facebook", "zalo", "tiktok", "direct", "email", "instagram"]
    utm_campaigns = ["tet_2026", "summer_sale", "brand_awareness", "flash_sale_1111", "retargeting_vip", "black_friday"]
    devices = ["Desktop", "Mobile_iOS", "Mobile_Android", "Tablet"]

    for sess_id in range(1, num_sessions + 1):
        cust_id = random.randint(1, num_customers) if random.random() > 0.15 else None
        store_id = random.randint(1, 10)
        channel_id = random.randint(1, 5)
        order_id = sess_id if sess_id <= num_orders else None

        token = f"sess_token_{sess_id:06d}_{random.randint(1000, 9999)}"
        utm_s = random.choice(utm_sources)
        utm_c = random.choice(utm_campaigns)
        dev = random.choice(devices)
        is_bot = '1' if sess_id % 30 == 0 else '0'  # ~3% bot traffic for filtering check

        has_cart = '1' if order_id or random.random() > 0.35 else '0'
        reached_chk = '1' if order_id or (has_cart == '1' and random.random() > 0.4) else '0'
        completed_chk = '1' if order_id else '0'

        days_ago = random.randint(1, 180)
        created_dt = datetime.now() - timedelta(days=days_ago, hours=random.randint(0, 23))
        created_str = created_dt.strftime("%Y-%m-%d %H:%M:%S")

        cust_str = str(cust_id) if cust_id else "NULL"
        order_str = str(order_id) if order_id else "NULL"

        web_sessions.append(
            f"({sess_id}, {cust_str}, {channel_id}, {store_id}, {order_str}, '{token}', '{utm_s}', '{utm_c}', 'google.com', "
            f"'{dev}', '{is_bot}', {random.randint(1, 20)}, {random.randint(20, 1500)}, '{has_cart}', '{reached_chk}', '{completed_chk}', '{created_str}')"
        )

        if has_cart == '1' and len(carts) < 6000:
            carts.append(f"({len(carts)+1}, {cust_str}, {store_id}, {sess_id}, '{completed_chk}', '{created_str}')")

    sql.append("INSERT INTO Web_Session (ID, Customer_ID, Sales_Channel_ID, Store_ID, Order_ID, Session_Token, UTM_Source, UTM_Campaign, Referrer_Source, Device_Type, Is_Bot_Traffic, Pageviews_Count, Session_Duration_Seconds, Has_Cart_Addition, Reached_Checkout, Completed_Checkout, Created_Time) VALUES\n" + ",\n".join(web_sessions) + ";")
    sql.append("INSERT INTO Cart (ID, Customer_ID, Store_ID, Web_Session_ID, Is_Checkout_Completed, Created_Time) VALUES\n" + ",\n".join(carts) + ";")

    return "\n".join(sql) + "\n\n"


def generate_seed_sql_file() -> str:
    """Combine all SQL parts and write to output file."""
    random.seed(42)
    content = []
    content.append(generate_header())
    content.append(generate_geography_sql())
    content.append(generate_lookups_sql())
    content.append(generate_employees_sql(count=50))
    content.append(generate_stores_sql())
    content.append(generate_categories_suppliers_and_taxes())
    content.append(generate_items_and_prices(count=200))
    content.append(generate_customers_sql(count=1000))
    content.append(generate_discounts_taxes_and_terms())
    content.append(generate_orders_and_analytics(num_orders=5000, num_customers=1000, num_products=200))
    content.append(generate_web_sessions_and_carts(num_sessions=8000, num_orders=5000, num_customers=1000))
    content.append(generate_footer())

    full_sql = "".join(content)
    with open(OUTPUT_SQL_PATH, "w", encoding="utf-8") as f:
        f.write(full_sql)

    return full_sql


def main() -> None:
    """Main entry point."""
    print("🚀 Generating massive seed dataset for ALL 36 TABLES in Golden Retail Database...")
    sql_text = generate_seed_sql_file()
    size_mb = len(sql_text.encode('utf-8')) / (1024 * 1024)
    print(f"✅ Successfully generated file at: {OUTPUT_SQL_PATH}")
    print(f"📊 Total file size: {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
