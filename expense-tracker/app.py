from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    Response
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from database import get_db_connection, init_db

from datetime import datetime, date

import csv
import io


app = Flask(__name__)

# Secret key for login sessions
app.secret_key = "expense-tracker-secret-key"


# Create database tables
init_db()


# =========================================================
# LOGIN REQUIRED
# =========================================================

def login_required():
    return "user_id" in session


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        # Check username
        if not username:
            flash(
                "Username is required.",
                "error"
            )

            return render_template(
                "register.html"
            )

        # Check password
        if len(password) < 6:
            flash(
                "Password must be at least 6 characters.",
                "error"
            )

            return render_template(
                "register.html"
            )

        # Check password confirmation
        if password != confirm_password:
            flash(
                "Passwords do not match.",
                "error"
            )

            return render_template(
                "register.html"
            )

        connection = get_db_connection()

        # Check if username already exists
        existing_user = connection.execute(
            """
            SELECT id
            FROM users
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        if existing_user:

            connection.close()

            flash(
                "Username already exists.",
                "error"
            )

            return render_template(
                "register.html"
            )

        # Hash password
        password_hash = generate_password_hash(
            password
        )

        created_at = datetime.now().isoformat()

        connection.execute(
            """
            INSERT INTO users
            (
                username,
                password_hash,
                created_at
            )
            VALUES (?, ?, ?)
            """,
            (
                username,
                password_hash,
                created_at
            )
        )

        connection.commit()
        connection.close()

        flash(
            "Account created successfully. Please login.",
            "success"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if "user_id" in session:
        return redirect(
            url_for("dashboard")
        )

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        connection = get_db_connection()

        user = connection.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        connection.close()

        if user and check_password_hash(
            user["password_hash"],
            password
        ):

            session.clear()

            session["user_id"] = user["id"]

            session["username"] = user["username"]

            flash(
                "Login successful!",
                "success"
            )

            return redirect(
                url_for("dashboard")
            )

        flash(
            "Invalid username or password.",
            "error"
        )

    return render_template(
        "login.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(
        url_for("login")
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if not login_required():
        return redirect(
            url_for("login")
        )

    user_id = session["user_id"]

    connection = get_db_connection()

    # Total spending
    total_result = connection.execute(
        """
        SELECT COALESCE(
            SUM(amount),
            0
        ) AS total
        FROM expenses
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()

    total_spending = total_result["total"] or 0

    # Current month
    current_month = date.today().strftime(
        "%Y-%m"
    )

    monthly_result = connection.execute(
        """
        SELECT COALESCE(
            SUM(amount),
            0
        ) AS total
        FROM expenses
        WHERE user_id = ?
        AND substr(expense_date, 1, 7) = ?
        """,
        (
            user_id,
            current_month
        )
    ).fetchone()

    monthly_spending = (
        monthly_result["total"] or 0
    )

    # Expense count
    count_result = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM expenses
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()

    expense_count = count_result["count"]

    # Category summary
    category_summary = connection.execute(
        """
        SELECT
            category,
            SUM(amount) AS total
        FROM expenses
        WHERE user_id = ?
        GROUP BY category
        ORDER BY total DESC
        """,
        (user_id,)
    ).fetchall()

    # Recent expenses
    recent_expenses = connection.execute(
        """
        SELECT *
        FROM expenses
        WHERE user_id = ?
        ORDER BY expense_date DESC, id DESC
        LIMIT 5
        """,
        (user_id,)
    ).fetchall()

    # Current budget
    budget_result = connection.execute(
        """
        SELECT amount
        FROM budgets
        WHERE user_id = ?
        AND month = ?
        """,
        (
            user_id,
            current_month
        )
    ).fetchone()

    budget_amount = (
        budget_result["amount"]
        if budget_result
        else 0
    )

    # Budget percentage
    if budget_amount > 0:

        budget_percentage = (
            monthly_spending
            / budget_amount
        ) * 100

        # Prevent progress bar going beyond 100%
        budget_percentage = min(
            budget_percentage,
            100
        )

    else:

        budget_percentage = 0

    connection.close()

    return render_template(
        "dashboard.html",
        total_spending=total_spending,
        monthly_spending=monthly_spending,
        expense_count=expense_count,
        category_summary=category_summary,
        recent_expenses=recent_expenses,
        budget_amount=budget_amount,
        budget_percentage=budget_percentage
    )


# =========================================================
# VIEW EXPENSES
# =========================================================

@app.route("/expenses")
def expenses():

    if not login_required():
        return redirect(
            url_for("login")
        )

    user_id = session["user_id"]

    search = request.args.get(
        "search",
        ""
    ).strip()

    category = request.args.get(
        "category",
        ""
    ).strip()

    connection = get_db_connection()

    query = """
        SELECT *
        FROM expenses
        WHERE user_id = ?
    """

    parameters = [user_id]

    # Search
    if search:

        query += """
            AND (
                description LIKE ?
                OR category LIKE ?
            )
        """

        search_value = f"%{search}%"

        parameters.extend(
            [
                search_value,
                search_value
            ]
        )

    # Category filter
    if category:

        query += """
            AND category = ?
        """

        parameters.append(category)

    query += """
        ORDER BY expense_date DESC, id DESC
    """

    expenses_list = connection.execute(
        query,
        parameters
    ).fetchall()

    connection.close()

    return render_template(
        "expenses.html",
        expenses=expenses_list,
        search=search,
        category=category
    )


# =========================================================
# ADD EXPENSE
# =========================================================

@app.route(
    "/expense/add",
    methods=["GET", "POST"]
)
def add_expense():

    if not login_required():
        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        amount_text = request.form.get(
            "amount",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        expense_date = request.form.get(
            "expense_date",
            ""
        ).strip()

        # Validate amount
        try:

            amount = float(amount_text)

        except ValueError:

            flash(
                "Please enter a valid amount.",
                "error"
            )

            return render_template(
                "add_expense.html",
                today=date.today().isoformat()
            )

        if amount <= 0:

            flash(
                "Amount must be greater than zero.",
                "error"
            )

            return render_template(
                "add_expense.html",
                today=date.today().isoformat()
            )

        # Validate other fields
        if not category:

            flash(
                "Please select a category.",
                "error"
            )

            return render_template(
                "add_expense.html",
                today=date.today().isoformat()
            )

        if not description:

            flash(
                "Please enter a description.",
                "error"
            )

            return render_template(
                "add_expense.html",
                today=date.today().isoformat()
            )

        if not expense_date:

            expense_date = date.today().isoformat()

        connection = get_db_connection()

        connection.execute(
            """
            INSERT INTO expenses
            (
                user_id,
                amount,
                category,
                description,
                expense_date,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                amount,
                category,
                description,
                expense_date,
                datetime.now().isoformat()
            )
        )

        connection.commit()
        connection.close()

        flash(
            "Expense added successfully!",
            "success"
        )

        return redirect(
            url_for("expenses")
        )

    return render_template(
        "add_expense.html",
        today=date.today().isoformat()
    )


# =========================================================
# EDIT EXPENSE
# =========================================================

@app.route(
    "/expense/edit/<int:expense_id>",
    methods=["GET", "POST"]
)
def edit_expense(expense_id):

    if not login_required():
        return redirect(
            url_for("login")
        )

    user_id = session["user_id"]

    connection = get_db_connection()

    expense = connection.execute(
        """
        SELECT *
        FROM expenses
        WHERE id = ?
        AND user_id = ?
        """,
        (
            expense_id,
            user_id
        )
    ).fetchone()

    if not expense:

        connection.close()

        flash(
            "Expense not found.",
            "error"
        )

        return redirect(
            url_for("expenses")
        )

    if request.method == "POST":

        amount_text = request.form.get(
            "amount",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        expense_date = request.form.get(
            "expense_date",
            ""
        ).strip()

        try:

            amount = float(amount_text)

        except ValueError:

            connection.close()

            flash(
                "Please enter a valid amount.",
                "error"
            )

            return redirect(
                url_for(
                    "edit_expense",
                    expense_id=expense_id
                )
            )

        if amount <= 0:

            connection.close()

            flash(
                "Amount must be greater than zero.",
                "error"
            )

            return redirect(
                url_for(
                    "edit_expense",
                    expense_id=expense_id
                )
            )

        if not category or not description:

            connection.close()

            flash(
                "Please fill in all fields.",
                "error"
            )

            return redirect(
                url_for(
                    "edit_expense",
                    expense_id=expense_id
                )
            )

        connection.execute(
            """
            UPDATE expenses

            SET
                amount = ?,
                category = ?,
                description = ?,
                expense_date = ?

            WHERE id = ?
            AND user_id = ?
            """,
            (
                amount,
                category,
                description,
                expense_date,
                expense_id,
                user_id
            )
        )

        connection.commit()
        connection.close()

        flash(
            "Expense updated successfully!",
            "success"
        )

        return redirect(
            url_for("expenses")
        )

    connection.close()

    return render_template(
        "edit_expense.html",
        expense=expense
    )


# =========================================================
# DELETE EXPENSE
# =========================================================

@app.route(
    "/expense/delete/<int:expense_id>",
    methods=["POST"]
)
def delete_expense(expense_id):

    if not login_required():
        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    connection.execute(
        """
        DELETE FROM expenses
        WHERE id = ?
        AND user_id = ?
        """,
        (
            expense_id,
            session["user_id"]
        )
    )

    connection.commit()
    connection.close()

    flash(
        "Expense deleted successfully!",
        "success"
    )

    return redirect(
        url_for("expenses")
    )


# =========================================================
# BUDGET
# =========================================================

@app.route(
    "/budget",
    methods=["GET", "POST"]
)
def budget():

    if not login_required():
        return redirect(
            url_for("login")
        )

    user_id = session["user_id"]

    current_month = date.today().strftime(
        "%Y-%m"
    )

    connection = get_db_connection()

    if request.method == "POST":

        amount_text = request.form.get(
            "amount",
            ""
        ).strip()

        try:

            amount = float(amount_text)

        except ValueError:

            connection.close()

            flash(
                "Please enter a valid budget amount.",
                "error"
            )

            return redirect(
                url_for("budget")
            )

        if amount < 0:

            connection.close()

            flash(
                "Budget cannot be negative.",
                "error"
            )

            return redirect(
                url_for("budget")
            )

        existing_budget = connection.execute(
            """
            SELECT id
            FROM budgets
            WHERE user_id = ?
            AND month = ?
            """,
            (
                user_id,
                current_month
            )
        ).fetchone()

        if existing_budget:

            connection.execute(
                """
                UPDATE budgets
                SET amount = ?
                WHERE user_id = ?
                AND month = ?
                """,
                (
                    amount,
                    user_id,
                    current_month
                )
            )

        else:

            connection.execute(
                """
                INSERT INTO budgets
                (
                    user_id,
                    month,
                    amount
                )
                VALUES (?, ?, ?)
                """,
                (
                    user_id,
                    current_month,
                    amount
                )
            )

        connection.commit()

        flash(
            "Monthly budget saved successfully!",
            "success"
        )

    # Get current budget
    budget_result = connection.execute(
        """
        SELECT amount
        FROM budgets
        WHERE user_id = ?
        AND month = ?
        """,
        (
            user_id,
            current_month
        )
    ).fetchone()

    budget_amount = (
        budget_result["amount"]
        if budget_result
        else 0
    )

    # Get monthly spending
    spending_result = connection.execute(
        """
        SELECT COALESCE(
            SUM(amount),
            0
        ) AS total
        FROM expenses
        WHERE user_id = ?
        AND substr(expense_date, 1, 7) = ?
        """,
        (
            user_id,
            current_month
        )
    ).fetchone()

    monthly_spending = (
        spending_result["total"] or 0
    )

    # Remaining budget
    remaining_budget = (
        budget_amount - monthly_spending
    )

    # Percentage
    if budget_amount > 0:

        budget_percentage = (
            monthly_spending
            / budget_amount
        ) * 100

        budget_percentage = min(
            budget_percentage,
            100
        )

    else:

        budget_percentage = 0

    connection.close()

    return render_template(
        "budget.html",
        budget_amount=budget_amount,
        monthly_spending=monthly_spending,
        remaining_budget=remaining_budget,
        budget_percentage=budget_percentage
    )


# =========================================================
# EXPORT CSV
# =========================================================

@app.route("/export/csv")
def export_csv():

    if not login_required():
        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    expenses = connection.execute(
        """
        SELECT
            expense_date,
            category,
            description,
            amount
        FROM expenses
        WHERE user_id = ?
        ORDER BY expense_date DESC
        """,
        (session["user_id"],)
    ).fetchall()

    connection.close()

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow(
        [
            "Date",
            "Category",
            "Description",
            "Amount"
        ]
    )

    for expense in expenses:

        writer.writerow(
            [
                expense["expense_date"],
                expense["category"],
                expense["description"],
                expense["amount"]
            ]
        )

    csv_data = output.getvalue()

    output.close()

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=expenses.csv"
        }
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )