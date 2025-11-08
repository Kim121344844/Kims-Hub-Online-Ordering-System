CREATE DATABASE IF NOT EXISTS kims_hub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE kims_hub;

-- USERS TABLE
CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(100) NOT NULL UNIQUE,
  password VARCHAR(255) NOT NULL,
  role ENUM('user','admin') DEFAULT 'user',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ORDERS TABLE
CREATE TABLE IF NOT EXISTS orders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id VARCHAR(100) NOT NULL UNIQUE,
  user_email VARCHAR(100) NOT NULL,
  user_name VARCHAR(100),
  phone VARCHAR(30),
  address TEXT,
  postal VARCHAR(20),
  city VARCHAR(100),
  date DATETIME DEFAULT CURRENT_TIMESTAMP,
  items TEXT,
  total DECIMAL(10,2) NOT NULL,
  payment_method VARCHAR(50),
  payment_id VARCHAR(100),
  status VARCHAR(50) DEFAULT 'Processing'
);

-- FAVORITES TABLE (optional)
CREATE TABLE IF NOT EXISTS favorites (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_email VARCHAR(100) NOT NULL,
  item_name VARCHAR(100) NOT NULL,
  item_image VARCHAR(255)
);

-- CART TABLE (optional session backup)
CREATE TABLE IF NOT EXISTS cart (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_email VARCHAR(100) NOT NULL,
  item_name VARCHAR(100) NOT NULL,
  item_price DECIMAL(10,2) NOT NULL,
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PAYMENTS TABLE (optional tracking)
CREATE TABLE IF NOT EXISTS payments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  payment_id VARCHAR(100),
  order_id VARCHAR(100),
  user_email VARCHAR(100),
  payment_method VARCHAR(50),
  amount DECIMAL(10,2),
  status VARCHAR(50),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO users (name, email, password, role)
VALUES (
  'Admin',
  'admin@admin.com',
  'pbkdf2:sha256:600000$8aR4Km9F2BZT$1b51e8d6b03e7e48b2e1cc91f76a9f99a9ac7fd0d8f4b3a263a31e1f52a37c1e',
  'admin'
);
