import sqlite3

connection = sqlite3.connect("expense_tracker.db")
cursor = connection.cursor()

print("=== EXPENSE TRACKER ===")

login = input("Enter your login: ")

cursor.execute(
    "select id from accounts where login = ?",
    (login,)
)

account = cursor.fetchone()

if account is None:
    print("Login not found.")

else:
    account_id = account[0]

    print("Welcome,", login)

    while True:

        print("\n===== MENU =====")
        print("1. Add expense")
        print("2. View my expenses")
        print("3. View total spending")
        print("4. Quit")

        choice = input("Choose an option: ")

        if choice == "1":

            amount = float(input("Enter amount: "))
            description = input("Enter description: ")

            print("\nCategories:")
            print("1. Food")
            print("2. Transport")
            print("3. Shopping")
            print("4. Entertainment")
            print("5. Bills")

            category_id = int(input("Choose category number: "))

            expense_date = input("Enter date (YYYY-MM-DD): ")

            cursor.execute(
                """
                insert into expenses
                (amount, description, expense_date, account_id, category_id)
                values (?, ?, ?, ?, ?)
                """,
                (
                    amount,
                    description,
                    expense_date,
                    account_id,
                    category_id
                )
            )

            connection.commit()

            print("Expense added successfully!")

        elif choice == "2":

            cursor.execute(
                """
                select
                    expenses.id,
                    amount,
                    description,
                    expense_date,
                    category_name
                from expenses
                join categories
                on expenses.category_id = categories.id
                where account_id = ?
                order by expenses.id desc
                """,
                (account_id,)
            )

            expenses = cursor.fetchall()

            if len(expenses) == 0:
                print("No expenses found.")

            else:
                print("\n=== YOUR EXPENSES ===")

                for expense in expenses:

                    print(
                        "ID:",
                        expense[0],
                        "| Amount:$",
                        expense[1],
                        "| Description:",
                        expense[2],
                        "| Date:",
                        expense[3],
                        "| Category:",
                        expense[4]
                    )

        elif choice == "3":

            cursor.execute(
                """
                select sum(amount)
                from expenses
                where account_id = ?
                """,
                (account_id,)
            )

            total = cursor.fetchone()[0]

            if total is None:
                total = 0

            print("\nTotal spending: $", total)

        elif choice == "4":

            print("Goodbye!")
            break

        else:
            print("Invalid option.")

connection.close()