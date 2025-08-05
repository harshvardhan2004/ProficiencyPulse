# 📊 ProficiencyPulse

A Full Stack Web App to track, visualize, and manage team skills across different domains, roles, and experience levels.  
Built to help project managers, HRs, and teams understand their **competency matrix** in real-time.

## 🚀 Features

- 🔍 **Skill Matrix Dashboard** – View team skills, levels, and gaps in one place  
- 👨‍💼 **Role-Based Access** – Admins can edit; users can only view  
- 🧠 **Smart Search** – Filter by skill, level, or employee  
- ✏️ **Skill Editing** – Add/remove/update employee skills  
- 📦 **REST API backend** – Clean, modular Flask + SQLAlchemy  
- 📈 **Scalable DB** – MySQL used for reliability and performance

## 🛠️ Tech Stack

| Layer        | Technology                |
|--------------|----------------------------|
| Frontend     | HTML5, CSS3, Bootstrap     |
| Backend      | Python Flask               |
| Database     | MySQL                      |
| ORM          | SQLAlchemy                 |
| Deployment   | Localhost (can scale to AWS, Heroku) |
| Version Ctrl | Git, GitHub                |

## 📂 Folder Structure

```
ProficiencyPulse/
├── app.py
├── templates/
│   ├── index.html
│   └── ...
├── static/
│   └── styles.css
├── database.py
├── config.env
└── README.md
```

## ⚙️ Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/harshvardhan2004/ProficiencyPulse.git
cd ProficiencyPulse
```

### 2. Set up Python Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate   # On Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. MySQL Setup

Open MySQL Workbench and run:
```sql
CREATE DATABASE skills_matrix;
CREATE USER 'skills'@'localhost' IDENTIFIED BY 'skills';
GRANT ALL PRIVILEGES ON skills_matrix.* TO 'skills'@'localhost';
```

### 5. Run App

```bash
python app.py
```

Visit: `http://localhost:5000`

## 📸 Screenshots

_Add your own screenshots here for extra credibility._

## 📚 Use Cases

- Used by HRs to identify skill gaps for hiring  
- Teams use it for self-evaluation  
- Managers use it for project allocation based on expertise

## 💡 Future Enhancements

- Login/Auth System (JWT or Flask-Login)  
- Skill Recommendations using ML  
- Export to Excel/CSV  
- Deploy to AWS or Heroku

## 👨‍💻 Author

**Harsh Vardhan**  
[GitHub](https://github.com/harshvardhan2004) | [LinkedIn](#)

## 🛡️ License

This project is open-source. Free to use with credits.

## ✅ Tip for Interview:
When asked, say:
> “I built this to simulate a real-world internal tool that companies use to manage teams. I used Flask and MySQL because that’s commonly used in backend-heavy startups. I wrote the whole thing myself and made it extensible so it can scale with features like user login and analytics.”