-- PostgreSQL Compatible Schema for Golden Retail Benchmark

-- ==============================================================================
-- GOLDEN BENCHMARK DATABASE SCHEMA: MULTI-STORE RETAIL & E-COMMERCE ERP
-- Target Engine: MySQL / MariaDB (Supports PostgreSQL conversion easily)
-- Purpose: Benchmark dataset for AI Semantic Layer Agent & Business Analytics
-- Includes: Core Master Data, Sales, Orders, Customers, Inventory, Taxes, Discounts,
--           Loyalty Programs, Employees, Carts, and Digital Web Analytics.
-- ==============================================================================

-- Drop database if recreating (Optional)
-- CREATE DATABASE IF NOT EXISTS golden_retail_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- USE golden_retail_db;

-- ------------------------------------------------------------------------------
-- MODULE 1: GEOGRAPHY & TIMEZONES
-- ------------------------------------------------------------------------------

CREATE TABLE Time_Zone (
    ID SERIAL,
    Name varchar(50) NOT NULL UNIQUE,
    Description varchar(255),
    PRIMARY KEY (ID)
);

CREATE TABLE Country (
    ID SERIAL,
    Name varchar(50) NOT NULL UNIQUE,
    PRIMARY KEY (ID)
);

CREATE TABLE Region (
    ID SERIAL,
    Name varchar(50) NOT NULL,
    Country_ID INT NOT NULL,
    PRIMARY KEY (ID),
    CONSTRAINT UK_Region UNIQUE (Name, Country_ID)
);

CREATE TABLE City (
    ID SERIAL,
    Name varchar(50) NOT NULL,
    Region_ID INT NOT NULL,
    Time_Zone_ID INT NOT NULL,
    Zip_Code INT,
    PRIMARY KEY (ID),
    CONSTRAINT UK_City UNIQUE (Name, Region_ID)
);

-- ------------------------------------------------------------------------------
-- MODULE 2: SYSTEM LOOKUPS & STORE SETTINGS
-- ------------------------------------------------------------------------------

CREATE TABLE Language (
    ID SERIAL,
    Name varchar(50) NOT NULL UNIQUE,
    Short_Name varchar(15) NOT NULL UNIQUE,
    Description varchar(255),
    PRIMARY KEY (ID)
);

CREATE TABLE Currency (
    ID SERIAL,
    Name varchar(50) NOT NULL UNIQUE,
    Short_Name varchar(15) NOT NULL UNIQUE,
    Symbol varchar(5) NOT NULL UNIQUE,
    Description varchar(255),
    PRIMARY KEY (ID)
);

CREATE TABLE Unit_Of_Measure (
    ID SERIAL,
    Name varchar(50) NOT NULL UNIQUE,
    Symbol varchar(15) NOT NULL UNIQUE,
    Description varchar(255),
    PRIMARY KEY (ID)
);

-- ------------------------------------------------------------------------------
-- MODULE 3: EMPLOYEES & ROLES
-- ------------------------------------------------------------------------------

CREATE TABLE Employee_Role (
    ID SERIAL,
    Name varchar(50) NOT NULL UNIQUE,
    Description varchar(255),
    Is_Active varchar(1) NOT NULL DEFAULT '1',
    PRIMARY KEY (ID)
);

CREATE TABLE Employee (
    ID SERIAL,
    Employee_Role_ID INT NOT NULL,
    Code varchar(25) NOT NULL UNIQUE,
    First_Name varchar(50) NOT NULL,
    Last_Name varchar(50) NOT NULL,
    Email varchar(50) UNIQUE,
    Phone varchar(50),
    Is_Active varchar(1) NOT NULL DEFAULT '1',
    PRIMARY KEY (ID)
);

CREATE TABLE Store (
    ID SERIAL,
    City_ID INT NOT NULL,
    Language_ID INT NOT NULL,
    Currency_ID INT NOT NULL,
    Admin_User_ID INT NOT NULL, -- FK to Employee.ID
    Code varchar(25) UNIQUE,
    Name varchar(50) NOT NULL UNIQUE,
    Is_Active varchar(1) NOT NULL,
    Legal_Entity_Name varchar(255) NOT NULL,
    Tax_Code varchar(50) NOT NULL,
    Address varchar(255) NOT NULL,
    Registration_Number varchar(50) NOT NULL,
    GPS_Location varchar(50),
    Postal_Code varchar(50),
    Phone varchar(50),
    Fax varchar(50),
    Email varchar(50),
    Website varchar(255),
    Logo BYTEA,
    Bank_Branch varchar(255),
    Bank_Code varchar(50),
    Bank_Account varchar(50),
    Comments varchar(1000),
    PRIMARY KEY (ID)
);

CREATE TABLE Employee_Login (
    ID SERIAL,
    Employee_ID INT NOT NULL,
    Employee_Role_ID INT NOT NULL,
    Login_Time timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Logout_Time timestamp NULL,
    Device_IP varchar(50) NOT NULL,
    Comments varchar(1000),
    PRIMARY KEY (ID)
);

-- ------------------------------------------------------------------------------
-- MODULE 4: PRODUCTS, SUPPLIERS & INVENTORY
-- ------------------------------------------------------------------------------

CREATE TABLE Item_Category (
    ID SERIAL,
    Parent_Category_ID INT,
    Name varchar(50) NOT NULL UNIQUE,
    Description varchar(255),
    Is_Active varchar(1) NOT NULL,
    Comments varchar(1000),
    PRIMARY KEY (ID)
);

CREATE TABLE Supplier (
    ID SERIAL,
    Store_ID INT NOT NULL,
    City_ID INT NOT NULL,
    Code varchar(10) NOT NULL UNIQUE,
    Phone varchar(50) NOT NULL,
    First_Name varchar(50) NOT NULL,
    Last_Name varchar(50) NOT NULL,
    Is_Company varchar(1) NOT NULL,
    Company_Name varchar(255),
    Tax_Number varchar(50),
    Is_Tax_Exempted varchar(1) NOT NULL,
    Billing_Address varchar(255) NOT NULL,
    Postal_Code varchar(50),
    Email varchar(50) NOT NULL,
    Created_Emp_Login_ID INT NOT NULL,
    Created_Time timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Is_Active varchar(1) NOT NULL,
    Comments varchar(1000),
    PRIMARY KEY (ID)
);

CREATE TABLE Item (
    ID SERIAL,
    Store_ID INT NOT NULL,
    Item_Category_ID INT NOT NULL,
    Supplier_ID INT NOT NULL,
    Unit_Of_Measure_ID INT NOT NULL,
    SKU_Code varchar(25) NOT NULL UNIQUE,
    Name varchar(50) NOT NULL,
    Description varchar(255),
    Is_Service varchar(1) NOT NULL,
    In_Stock varchar(1) NOT NULL,
    Using_Default_Quantity varchar(1) NOT NULL,
    Default_Quantity INT,
    Current_Stock_Quantity INT NOT NULL,
    Preferred_Stock_Quantity INT NOT NULL,
    Min_Stock_Quantity INT NOT NULL,
    Low_Stock_Warning varchar(1) NOT NULL,
    Low_Stock_Quantity INT,
    Is_Active varchar(1) NOT NULL,
    Comments varchar(1000),
    PRIMARY KEY (ID)
);

CREATE TABLE Bar_Code (
    ID SERIAL,
    Item_ID INT NOT NULL,
    Bar_Code BYTEA NOT NULL,
    Is_Active varchar(1) NOT NULL,
    Description varchar(255),
    PRIMARY KEY (ID)
);

CREATE TABLE Price (
    ID SERIAL,
    Item_ID INT NOT NULL,
    Store_ID INT NOT NULL,
    Description varchar(255),
    Current_Item_Cost decimal(15, 3) NOT NULL,
    Markup_percentage INT NOT NULL,
    Price_Before_Tax decimal(15, 3) NOT NULL,
    Tax_Value decimal(15, 3) NOT NULL,
    Price_After_Tax decimal(15, 3) NOT NULL,
    Sale_Price decimal(15, 3) NOT NULL,
    Price_Change_Allowed varchar(1) NOT NULL,
    Created_Time timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Created_Emp_Login_ID INT NOT NULL,
    Start_Time timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    End_Time timestamp NULL,
    Is_Active varchar(1) NOT NULL,
    Comments varchar(1000),
    PRIMARY KEY (ID)
);

-- ------------------------------------------------------------------------------
-- MODULE 5: CUSTOMERS & LOYALTY
-- ------------------------------------------------------------------------------

CREATE TABLE Customer (
    ID SERIAL,
    City_ID INT NOT NULL,
    Code varchar(25) NOT NULL,
    Phone varchar(50) NOT NULL UNIQUE,
    First_Name varchar(50) NOT NULL,
    Last_Name varchar(50) NOT NULL,
    Is_Company varchar(1) NOT NULL,
    Company_Name varchar(255),
    Tax_Number varchar(50),
    Is_Tax_Exempted varchar(1) NOT NULL,
    Billing_Address varchar(255) NOT NULL,
    Postal_Code varchar(50),
    Is_Registered_Online varchar(1) NOT NULL,
    Email varchar(50) UNIQUE,
    Username varchar(50) UNIQUE,
    Password BYTEA,
    Credit decimal(14, 2),
    Created_Emp_Login_ID INT,
    Created_At_Store_ID INT,
    Created_Time timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Last_Login_Time timestamp NULL,
    Is_Active varchar(1) NOT NULL,
    Comments varchar(1000),
    PRIMARY KEY (ID)
);

CREATE TABLE Loyalty_Card_Type (
    ID SERIAL,
    Name varchar(50) NOT NULL UNIQUE,
    Description varchar(255),
    Discount_Percentage decimal(5, 2) DEFAULT 0,
    Min_Accumulated_Points INT DEFAULT 0,
    Is_Active varchar(1) NOT NULL DEFAULT '1',
    PRIMARY KEY (ID)
);

CREATE TABLE Loyalty_Card (
    ID SERIAL,
    Customer_ID INT NOT NULL,
    Loyalty_Card_Type_ID INT NOT NULL,
    Card_Number varchar(50) NOT NULL UNIQUE,
    Total_Points INT NOT NULL DEFAULT 0,
    Issue_Date timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Is_Active varchar(1) NOT NULL DEFAULT '1',
    PRIMARY KEY (ID)
);

-- ------------------------------------------------------------------------------
-- MODULE 6: TAXES & DISCOUNTS
-- ------------------------------------------------------------------------------

CREATE TABLE Tax_Type (
    ID SERIAL,
    Store_ID INT NOT NULL,
    Name varchar(50) NOT NULL,
    Code varchar(25) NOT NULL,
    Description varchar(255),
    Is_Percentage varchar(1) NOT NULL,
    Value decimal(15, 3) NOT NULL,
    Created_Time timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Start_Time timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    End_Time timestamp NULL,
    Is_Active varchar(1) NOT NULL,
    Comments varchar(1000),
    PRIMARY KEY (ID),
    CONSTRAINT UK_Store_Name UNIQUE (Store_ID, Name),
    CONSTRAINT UK_Store_Code UNIQUE (Store_ID, Code)
);

CREATE TABLE Supplier_Tax_Type (
    ID SERIAL,
    Supplier_ID INT NOT NULL,
    Name varchar(50) NOT NULL,
    Code varchar(25) NOT NULL,
    Description varchar(255),
    Is_Percentage varchar(1) NOT NULL,
    Value decimal(15, 3) NOT NULL,
    Created_Time timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Start_Time timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    End_Time timestamp NULL,
    Is_Active varchar(1) NOT NULL,
    Comments varchar(1000),
    PRIMARY KEY (ID),
    CONSTRAINT UK_Supplier_Name UNIQUE (Supplier_ID, Name),
    CONSTRAINT UK_Supplier_Code UNIQUE (Supplier_ID, Code)
);

CREATE TABLE Supplier_Item_Tax_Type (
    ID SERIAL,
    Item_ID INT NOT NULL,
    Supplier_Tax_Type_ID INT NOT NULL,
    Created_Time timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Start_Time timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    End_Time timestamp NULL,
    Description varchar(255),
    PRIMARY KEY (ID)
);

CREATE TABLE Discount_Type (
    ID SERIAL,
    Store_ID INT NOT NULL,
    Name varchar(50) NOT NULL,
    Description varchar(255),
    Is_Percentage varchar(1) NOT NULL,
    Value decimal(15, 3) NOT NULL,
    Created_Time timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Start_Time timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    End_Time timestamp NULL,
    Loyalty_Card_Type_ID INT,
    Coupon_Code varchar(50),
    Min_Order_Value decimal(15, 3) NOT NULL,
    Min_Item_Quantity INT NOT NULL,
    Apply_To_All varchar(1) NOT NULL,
    Apply_To_Next varchar(1) NOT NULL,
    Max_Discount_Value decimal(15, 3) NOT NULL,
    Is_Active varchar(1) NOT NULL,
    Comments varchar(1000),
    PRIMARY KEY (ID)
);

CREATE TABLE Discount (
    ID SERIAL,
    Discount_Type_ID INT NOT NULL,
    Item_Category_ID INT,
    Item_ID INT,
    Description varchar(255),
    Comments varchar(1000),
    PRIMARY KEY (ID)
);

-- ------------------------------------------------------------------------------
-- MODULE 7: CHANNELS & PAYMENT TERMS
-- ------------------------------------------------------------------------------

CREATE TABLE Sales_Channel (
    ID SERIAL,
    Name varchar(50) NOT NULL UNIQUE,
    Description varchar(255),
    Is_Active varchar(1) NOT NULL,
    PRIMARY KEY (ID)
);

CREATE TABLE Delivery_Type (
    ID SERIAL,
    Name varchar(50) NOT NULL UNIQUE,
    Description varchar(255),
    Is_Active varchar(1) NOT NULL,
    PRIMARY KEY (ID)
);

CREATE TABLE Payment_Method (
    ID SERIAL,
    Name varchar(50) NOT NULL UNIQUE,
    Code varchar(25) NOT NULL UNIQUE,
    Sequence_No INT,
    Is_Active varchar(1) NOT NULL,
    Is_Customer_Required varchar(1) NOT NULL,
    Description varchar(255),
    PRIMARY KEY (ID)
);

CREATE TABLE Payment_Time (
    ID SERIAL,
    Name varchar(50) NOT NULL UNIQUE,
    Description varchar(255),
    Is_Active varchar(1) NOT NULL,
    PRIMARY KEY (ID)
);

CREATE TABLE Payment_Term (
    ID SERIAL,
    Sales_Channel_ID INT NOT NULL,
    Delivery_Type_ID INT NOT NULL,
    Payment_Method_ID INT NOT NULL,
    Payment_Time_ID INT NOT NULL,
    Is_Allowed varchar(1) NOT NULL,
    Is_Active varchar(1) NOT NULL,
    Comments varchar(1000),
    PRIMARY KEY (ID),
    CONSTRAINT UK_Payment_Term UNIQUE (Sales_Channel_ID, Delivery_Type_ID, Payment_Method_ID, Payment_Time_ID)
);

CREATE TABLE Setting (
    ID SERIAL,
    Store_ID INT NOT NULL,
    Default_Payment_Method_ID INT,
    Default_Tax_Type_ID INT,
    Default_Quantity INT,
    In_Stock_Check varchar(1) NOT NULL,
    Negative_Stock_Allowed varchar(1) NOT NULL,
    Price_Includes_Tax varchar(1) NOT NULL,
    Negative_Price_Allowed varchar(1) NOT NULL,
    Moving_Average_Price varchar(1) NOT NULL,
    Discount_Before_Tax varchar(1) NOT NULL,
    Default_Due_Days INT,
    Decimal_Places INT,
    Public_Reviews_Allowed varchar(1) NOT NULL,
    Created_Time timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Start_Time timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    End_Time timestamp NULL,
    Is_Active varchar(1) NOT NULL,
    Comments varchar(1000),
    PRIMARY KEY (ID)
);

-- ------------------------------------------------------------------------------
-- MODULE 8: ORDERS & TRANSACTIONS
-- ------------------------------------------------------------------------------

CREATE TABLE Order_Status (
    ID SERIAL,
    Name varchar(50) NOT NULL UNIQUE,
    Description varchar(255),
    Is_Active varchar(1) NOT NULL,
    PRIMARY KEY (ID)
);

CREATE TABLE Order_Header (
    ID SERIAL,
    Store_ID INT NOT NULL,
    Sales_Channel_ID INT NOT NULL,
    Delivery_Type_ID INT NOT NULL,
    Payment_Method_ID INT NOT NULL,
    Payment_Time_ID INT NOT NULL,
    Order_No varchar(50) NOT NULL UNIQUE,
    Customer_ID INT,
    Loyalty_Card_ID INT,
    Created_Emp_Login_ID INT,
    Created_Customer_ID INT,
    Created_Time timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Approved_Emp_Login_ID INT,
    Managed_Emp_Login_ID INT,
    Customer_Notes varchar(255),
    Price_Before_Tax decimal(15, 3) NOT NULL,
    Total_Tax_Value decimal(15, 3) NOT NULL,
    Price_After_Tax decimal(15, 3) NOT NULL,
    Price_Before_Discount decimal(15, 3) NOT NULL, -- Gross Amount
    Order_Items_Discount decimal(15, 3) NOT NULL,
    Order_Discount decimal(15, 3) NOT NULL,
    Total_Discount_Value decimal(15, 3) NOT NULL, -- Discount Amount
    Return_Amount decimal(15, 3) NOT NULL DEFAULT 0.000, -- Return Amount
    Price_After_Discount decimal(15, 3) NOT NULL,
    Price_Adjustment decimal(15, 3),
    Price_Adjustment_Reason varchar(255),
    Price decimal(15, 3) NOT NULL,
    Latest_Status varchar(50) NOT NULL,
    Latest_Status_Update timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Is_Test_Order varchar(1) NOT NULL DEFAULT '0', -- Cờ đơn hàng thử nghiệm (Filter out test orders)
    Customer_Order_Seq INT DEFAULT 1, -- Thứ tự đơn của KH (Phân loại New vs Returning)
    Is_Submitted varchar(1) NOT NULL,
    Submitted_Time timestamp NULL,
    Is_Approved varchar(1) NOT NULL,
    Approved_Time timestamp NULL,
    Is_Canceled varchar(1) NOT NULL,
    Canceled_Time timestamp NULL,
    Cancel_Reason varchar(255),
    Is_Scheduled varchar(1) NOT NULL,
    Scheduled_Time timestamp NULL,
    Is_Ready varchar(1) NOT NULL,
    Ready_Time timestamp NULL,
    Is_Delivered varchar(1) NOT NULL,
    Delivered_Time timestamp NULL,
    Is_Paid varchar(1) NOT NULL,
    Payment_Time timestamp NULL,
    Is_Completed varchar(1) NOT NULL,
    Completed_Time timestamp NULL,
    Return_Required varchar(1) NOT NULL,
    Return_Time timestamp NULL,
    Comments varchar(1000),
    PRIMARY KEY (ID)
);

CREATE TABLE Order_Line (
    ID SERIAL,
    Store_ID INT NOT NULL,
    Order_ID INT NOT NULL,
    Item_ID INT NOT NULL,
    Line_No varchar(50) NOT NULL,
    Description varchar(255),
    Customer_Notes varchar(255),
    Quantity INT NOT NULL,
    Current_Item_Cost decimal(15, 3) NOT NULL, -- Giá vốn COGS
    Markup_Percentage INT NOT NULL,
    Price_Before_Tax decimal(15, 3) NOT NULL,
    Tax_Value decimal(15, 3) NOT NULL,
    Price_After_Tax decimal(15, 3) NOT NULL,
    Price_Before_Discount decimal(15, 3) NOT NULL,
    Discount_Value decimal(15, 3) NOT NULL,
    Price_After_Discount decimal(15, 3) NOT NULL,
    Price_Adjustment decimal(15, 3),
    Price_Adjustment_Reason varchar(255),
    Price decimal(15, 3) NOT NULL,
    Is_Canceled varchar(1) NOT NULL,
    Canceled_Time timestamp NULL,
    Cancel_Reason varchar(255),
    Return_Required varchar(1) NOT NULL,
    Return_Quantity INT,
    Return_Time timestamp NULL,
    Customer_Review varchar(255),
    Customer_Like varchar(1),
    Comments varchar(1000),
    PRIMARY KEY (ID)
);

CREATE TABLE Order_Status_History (
    ID SERIAL,
    Order_ID INT NOT NULL,
    Order_Status_ID INT NOT NULL,
    Start_Time timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    End_Time timestamp NULL,
    PRIMARY KEY (ID)
);

-- ------------------------------------------------------------------------------
-- MODULE 9: CARTS, WEB TRAFFIC & BEHAVIOR ANALYTICS
-- ------------------------------------------------------------------------------

CREATE TABLE Web_Session (
    ID SERIAL,
    Customer_ID INT,
    Sales_Channel_ID INT,
    Store_ID INT,
    Order_ID INT, -- Linked order if converted
    Session_Token varchar(100) NOT NULL UNIQUE,
    UTM_Source varchar(100),
    UTM_Campaign varchar(100),
    Referrer_Source varchar(100),
    Device_Type varchar(50),
    Is_Bot_Traffic varchar(1) NOT NULL DEFAULT '0', -- Cờ bot traffic (is_bot_traffic = FALSE)
    Pageviews_Count INT DEFAULT 1,
    Session_Duration_Seconds INT DEFAULT 0,
    Has_Cart_Addition varchar(1) NOT NULL DEFAULT '0',
    Reached_Checkout varchar(1) NOT NULL DEFAULT '0',
    Completed_Checkout varchar(1) NOT NULL DEFAULT '0',
    Created_Time timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ID)
);

CREATE TABLE Cart (
    ID SERIAL,
    Customer_ID INT,
    Store_ID INT NOT NULL,
    Web_Session_ID INT,
    Is_Checkout_Completed varchar(1) NOT NULL DEFAULT '0', -- Checkout completed flag
    Created_Time timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ID)
);


-- ==============================================================================
-- FOREIGN KEY CONSTRAINTS (ALL RELATIONS DEFINED CLEANLY)
-- ==============================================================================

-- Geography & Store Links
ALTER TABLE Region ADD CONSTRAINT FK_Region_Country FOREIGN KEY (Country_ID) REFERENCES Country (ID);
ALTER TABLE City ADD CONSTRAINT FK_City_Region FOREIGN KEY (Region_ID) REFERENCES Region (ID);
ALTER TABLE City ADD CONSTRAINT FK_City_Time_Zone FOREIGN KEY (Time_Zone_ID) REFERENCES Time_Zone (ID);

-- Employees & Store Admin
ALTER TABLE Employee ADD CONSTRAINT FK_Employee_Role FOREIGN KEY (Employee_Role_ID) REFERENCES Employee_Role (ID);
ALTER TABLE Employee_Login ADD CONSTRAINT FK_Employee_Login_Employee FOREIGN KEY (Employee_ID) REFERENCES Employee (ID);
ALTER TABLE Employee_Login ADD CONSTRAINT FK_Employee_Login_Role FOREIGN KEY (Employee_Role_ID) REFERENCES Employee_Role (ID);

ALTER TABLE Store ADD CONSTRAINT FK_Store_City FOREIGN KEY (City_ID) REFERENCES City (ID);
ALTER TABLE Store ADD CONSTRAINT FK_Store_Currency FOREIGN KEY (Currency_ID) REFERENCES Currency (ID);
ALTER TABLE Store ADD CONSTRAINT FK_Store_Language FOREIGN KEY (Language_ID) REFERENCES Language (ID);
ALTER TABLE Store ADD CONSTRAINT FK_Store_Admin_User FOREIGN KEY (Admin_User_ID) REFERENCES Employee (ID);

-- Item & Supplier Links
ALTER TABLE Item_Category ADD CONSTRAINT FK_Item_Category_Parent FOREIGN KEY (Parent_Category_ID) REFERENCES Item_Category (ID);
ALTER TABLE Supplier ADD CONSTRAINT FK_Supplier_City FOREIGN KEY (City_ID) REFERENCES City (ID);
ALTER TABLE Supplier ADD CONSTRAINT FK_Supplier_Created_Emp_Login FOREIGN KEY (Created_Emp_Login_ID) REFERENCES Employee_Login (ID);
ALTER TABLE Supplier ADD CONSTRAINT FK_Supplier_Store FOREIGN KEY (Store_ID) REFERENCES Store (ID);

ALTER TABLE Item ADD CONSTRAINT FK_Item_Item_Category FOREIGN KEY (Item_Category_ID) REFERENCES Item_Category (ID);
ALTER TABLE Item ADD CONSTRAINT FK_Item_Store FOREIGN KEY (Store_ID) REFERENCES Store (ID);
ALTER TABLE Item ADD CONSTRAINT FK_Item_Supplier FOREIGN KEY (Supplier_ID) REFERENCES Supplier (ID);
ALTER TABLE Item ADD CONSTRAINT FK_Item_Unit_Of_Measure FOREIGN KEY (Unit_Of_Measure_ID) REFERENCES Unit_Of_Measure (ID);
ALTER TABLE Bar_Code ADD CONSTRAINT FK_Bar_Code_Item FOREIGN KEY (Item_ID) REFERENCES Item (ID);

ALTER TABLE Price ADD CONSTRAINT FK_Price_Employee_Login FOREIGN KEY (Created_Emp_Login_ID) REFERENCES Employee_Login (ID);
ALTER TABLE Price ADD CONSTRAINT FK_Price_Item FOREIGN KEY (Item_ID) REFERENCES Item (ID);
ALTER TABLE Price ADD CONSTRAINT FK_Price_Store FOREIGN KEY (Store_ID) REFERENCES Store (ID);

-- Customers & Loyalty Links
ALTER TABLE Customer ADD CONSTRAINT FK_Customer_City FOREIGN KEY (City_ID) REFERENCES City (ID);
ALTER TABLE Customer ADD CONSTRAINT FK_Customer_Created_Emp_Login FOREIGN KEY (Created_Emp_Login_ID) REFERENCES Employee_Login (ID);
ALTER TABLE Customer ADD CONSTRAINT FK_Customer_Store FOREIGN KEY (Created_At_Store_ID) REFERENCES Store (ID);

ALTER TABLE Loyalty_Card ADD CONSTRAINT FK_Loyalty_Card_Customer FOREIGN KEY (Customer_ID) REFERENCES Customer (ID);
ALTER TABLE Loyalty_Card ADD CONSTRAINT FK_Loyalty_Card_Type FOREIGN KEY (Loyalty_Card_Type_ID) REFERENCES Loyalty_Card_Type (ID);

-- Discounts & Taxes Links
ALTER TABLE Discount_Type ADD CONSTRAINT FK_Discount_Type_Store FOREIGN KEY (Store_ID) REFERENCES Store (ID);
ALTER TABLE Discount_Type ADD CONSTRAINT FK_Discount_Type_Loyalty_Card_Type FOREIGN KEY (Loyalty_Card_Type_ID) REFERENCES Loyalty_Card_Type (ID);
ALTER TABLE Discount ADD CONSTRAINT FK_Discount_Discount_Type FOREIGN KEY (Discount_Type_ID) REFERENCES Discount_Type (ID);
ALTER TABLE Discount ADD CONSTRAINT FK_Discount_Item FOREIGN KEY (Item_ID) REFERENCES Item (ID);
ALTER TABLE Discount ADD CONSTRAINT FK_Discount_Item_Category FOREIGN KEY (Item_Category_ID) REFERENCES Item_Category (ID);

ALTER TABLE Tax_Type ADD CONSTRAINT FK_Tax_Type_Store FOREIGN KEY (Store_ID) REFERENCES Store (ID);
ALTER TABLE Supplier_Tax_Type ADD CONSTRAINT FK_Supplier_Tax_Type_Supplier FOREIGN KEY (Supplier_ID) REFERENCES Supplier (ID);
ALTER TABLE Supplier_Item_Tax_Type ADD CONSTRAINT FK_Supplier_Item_Tax_Type_Item FOREIGN KEY (Item_ID) REFERENCES Item (ID);
ALTER TABLE Supplier_Item_Tax_Type ADD CONSTRAINT FK_Supplier_Item_Tax_Type_Supplier_Tax_Type FOREIGN KEY (Supplier_Tax_Type_ID) REFERENCES Supplier_Tax_Type (ID);

-- Payment Terms Links
ALTER TABLE Payment_Term ADD CONSTRAINT FK_Payment_Term_Delivery_Type FOREIGN KEY (Delivery_Type_ID) REFERENCES Delivery_Type (ID);
ALTER TABLE Payment_Term ADD CONSTRAINT FK_Payment_Term_Payment_Method FOREIGN KEY (Payment_Method_ID) REFERENCES Payment_Method (ID);
ALTER TABLE Payment_Term ADD CONSTRAINT FK_Payment_Term_Payment_Time FOREIGN KEY (Payment_Time_ID) REFERENCES Payment_Time (ID);
ALTER TABLE Payment_Term ADD CONSTRAINT FK_Payment_Term_Sales_Channel FOREIGN KEY (Sales_Channel_ID) REFERENCES Sales_Channel (ID);

ALTER TABLE Setting ADD CONSTRAINT FK_Setting_Payment_Method FOREIGN KEY (Default_Payment_Method_ID) REFERENCES Payment_Method (ID);
ALTER TABLE Setting ADD CONSTRAINT FK_Setting_Store FOREIGN KEY (Store_ID) REFERENCES Store (ID);
ALTER TABLE Setting ADD CONSTRAINT FK_Setting_Tax_Type FOREIGN KEY (Default_Tax_Type_ID) REFERENCES Tax_Type (ID);

-- Orders Links
ALTER TABLE Order_Header ADD CONSTRAINT FK_Order_Approved_Emp_Login FOREIGN KEY (Approved_Emp_Login_ID) REFERENCES Employee_Login (ID);
ALTER TABLE Order_Header ADD CONSTRAINT FK_Order_Created_Customer FOREIGN KEY (Created_Customer_ID) REFERENCES Customer (ID);
ALTER TABLE Order_Header ADD CONSTRAINT FK_Order_Created_Emp_Login FOREIGN KEY (Created_Emp_Login_ID) REFERENCES Employee_Login (ID);
ALTER TABLE Order_Header ADD CONSTRAINT FK_Order_Customer FOREIGN KEY (Customer_ID) REFERENCES Customer (ID);
ALTER TABLE Order_Header ADD CONSTRAINT FK_Order_Delivery_Type FOREIGN KEY (Delivery_Type_ID) REFERENCES Delivery_Type (ID);
ALTER TABLE Order_Header ADD CONSTRAINT FK_Order_Loyalty_Card FOREIGN KEY (Loyalty_Card_ID) REFERENCES Loyalty_Card (ID);
ALTER TABLE Order_Header ADD CONSTRAINT FK_Order_Managed_Emp_Login FOREIGN KEY (Managed_Emp_Login_ID) REFERENCES Employee_Login (ID);
ALTER TABLE Order_Header ADD CONSTRAINT FK_Order_Payment_Method FOREIGN KEY (Payment_Method_ID) REFERENCES Payment_Method (ID);
ALTER TABLE Order_Header ADD CONSTRAINT FK_Order_Payment_Time FOREIGN KEY (Payment_Time_ID) REFERENCES Payment_Time (ID);
ALTER TABLE Order_Header ADD CONSTRAINT FK_Order_Sales_Channel FOREIGN KEY (Sales_Channel_ID) REFERENCES Sales_Channel (ID);
ALTER TABLE Order_Header ADD CONSTRAINT FK_Order_Store FOREIGN KEY (Store_ID) REFERENCES Store (ID);

ALTER TABLE Order_Line ADD CONSTRAINT FK_Order_Line_Item FOREIGN KEY (Item_ID) REFERENCES Item (ID);
ALTER TABLE Order_Line ADD CONSTRAINT FK_Order_Line_Order FOREIGN KEY (Order_ID) REFERENCES Order_Header (ID);
ALTER TABLE Order_Line ADD CONSTRAINT FK_Order_Line_Store FOREIGN KEY (Store_ID) REFERENCES Store (ID);

ALTER TABLE Order_Status_History ADD CONSTRAINT FK_Order_Status_History_Order FOREIGN KEY (Order_ID) REFERENCES Order_Header (ID);
ALTER TABLE Order_Status_History ADD CONSTRAINT FK_Order_Status_History_Order_Status FOREIGN KEY (Order_Status_ID) REFERENCES Order_Status (ID);

-- Web Sessions & Carts Links
ALTER TABLE Web_Session ADD CONSTRAINT FK_Web_Session_Customer FOREIGN KEY (Customer_ID) REFERENCES Customer (ID);
ALTER TABLE Web_Session ADD CONSTRAINT FK_Web_Session_Sales_Channel FOREIGN KEY (Sales_Channel_ID) REFERENCES Sales_Channel (ID);
ALTER TABLE Web_Session ADD CONSTRAINT FK_Web_Session_Store FOREIGN KEY (Store_ID) REFERENCES Store (ID);
ALTER TABLE Web_Session ADD CONSTRAINT FK_Web_Session_Order FOREIGN KEY (Order_ID) REFERENCES Order_Header (ID);

ALTER TABLE Cart ADD CONSTRAINT FK_Cart_Customer FOREIGN KEY (Customer_ID) REFERENCES Customer (ID);
ALTER TABLE Cart ADD CONSTRAINT FK_Cart_Store FOREIGN KEY (Store_ID) REFERENCES Store (ID);
ALTER TABLE Cart ADD CONSTRAINT FK_Cart_Web_Session FOREIGN KEY (Web_Session_ID) REFERENCES Web_Session (ID);
