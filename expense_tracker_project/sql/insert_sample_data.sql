use expense_tracker;

insert into accounts (login)
values
('account1'),
('account2'),
('account3');

insert into categories (category_name)
values
('Food'),
('Transport'),
('Shopping'),
('Entertainment'),
('Bills');

insert into expenses (
    amount,
    description,
    expense_date,
    account_id,
    category_id
)
values
(10.00, 'Lunch', '2026-05-10', 1, 1),
(20.00, 'Bus ticket', '2026-05-10', 1, 2),
(50.00, 'Clothes', '2026-05-10', 2, 3);

insert into budgets (
    account_id,
    category_id,
    monthly_limit
)
values
(1, 1, 200.00),
(1, 2, 100.00),
(2, 3, 150.00);