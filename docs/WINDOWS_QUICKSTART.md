# Quickstart cho Windows (PowerShell, không cần `make`)

Các lệnh dưới đây tương đương với `make setup / preflight / test / run`.

```powershell
# 1. Tạo môi trường (Python 3.11-3.13)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Kiểm tra môi trường, fixtures, offline guard
python -m tools.preflight

# 3. Chạy test
python -m pytest -q

# 4. Chạy pipeline của nhóm (offline, seed cố định)
python -m src.main --input fixtures/t02_raw_qc --config configs/lab.yaml --output out/ --offline --seed 42
```

Mẹo:
- Nếu PowerShell chặn script kích hoạt venv: `Set-ExecutionPolicy -Scope Process Bypass`.
- Nếu mạng bị chặn, cài từ thư mục wheel local: `pip install --no-index --find-links wheelhouse -r requirements.txt`.
- Thư mục `out/`, `.venv/` và `wheelhouse/` đã nằm trong `.gitignore`, không commit chúng.
- Nhớ đặt `git config user.name/user.email` để `git shortlog -sne --all` khớp `reports/team_contributions.csv`.
