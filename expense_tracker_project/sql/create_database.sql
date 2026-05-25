drop database if exists expense_tracker;

create database expense_tracker;

use expense_tracker;

create table accounts (
    id int primary key auto_increment,
    login varchar(50) unique not null
);

create table categories (
    id int primary key auto_increment,
    category_name varchar(50) unique not null
);

create table expenses (
    id int primary key auto_increment,
    amount decimal(10,2) not null,
    description varchar(100),
    expense_date date not null,
    account_id int not null,
    category_id int not null,
    foreign key (account_id) references accounts(id),
    foreign key (category_id) references categories(id)
);

create table budgets (
    id int primary key auto_increment,
    account_id int not null,
    category_id int not null,
    monthly_limit decimal(10,2) not null,
    foreign key (account_id) references accounts(id),
    foreign key (category_id) references categories(id)
);