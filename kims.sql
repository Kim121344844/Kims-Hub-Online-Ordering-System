CREATE DATABASE IF NOT EXISTS kims CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE kims;

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

INSERT INTO users (name, email, password, role)
VALUES (
  'Admin',
  'admin@admin.com',
  'pbkdf2:sha256:600000$8aR4Km9F2BZT$1b51e8d6b03e7e48b2e1cc91f76a9f99a9ac7fd0d8f4b3a263a31e1f52a37c1e',
  'admin'
);

-- OTP TABLE
CREATE TABLE IF NOT EXISTS otp_verification (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(100) NOT NULL,
    otp VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

