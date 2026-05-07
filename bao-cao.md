# Báo cáo Lab MLOps — Day 21 Track 2 (CI/CD for AI Systems)

**Sinh viên**: Trần Nhật Hoàng — `tnhoang462@gmail.com`
**Repo**: https://github.com/tnhoang462/Day21-Track2-CI-CD-for-AI-Systems
**Cloud**: Google Cloud Platform — project `project-2be04881-882a-4625-897`, region `asia-southeast1`

---

## 1. Bộ siêu tham số đã chọn (kết quả Bước 1)

5 thí nghiệm trên `train_phase1.csv` (2998 mẫu):

| Run | n_estimators | max_depth | min_samples_split | accuracy | f1_score |
|---|---|---|---|---|---|
| 1 | 100 | 5 | 2 | 0.564 | 0.553 |
| 2 | 50 | 3 | 2 | 0.558 | 0.519 |
| **3 (best)** | **200** | **20** | **2** | **0.684** | **0.683** |
| 4 | 500 | 30 | 2 | 0.680 | 0.679 |
| 5 | 300 | 25 | 5 | 0.668 | 0.666 |

**Lý do chọn Run 3** (`n_estimators=200, max_depth=20, min_samples_split=2`):
- Bộ tham số sâu hơn (depth 20 vs 5) cho thấy mô hình học được pattern phức tạp hơn 6%-12% accuracy.
- Tăng tiếp lên 500 cây / depth 30 cho diminishing returns (0.680, đã overfitting nhẹ).
- Tăng `min_samples_split` lên 5 làm giảm độ chính xác → giữ giá trị mặc định 2.

Sau khi bổ sung dữ liệu ở Bước 3 (5996 mẫu), cùng bộ siêu tham số đạt **accuracy 0.748 (+6.4%)** chứng minh bộ params tốt còn nhiều dư địa cải thiện khi data scale lên.

---

## 2. Khó khăn gặp phải và cách giải quyết

### 2.1 Org policy chặn tạo Service Account JSON key
**Vấn đề**: Lệnh `gcloud iam service-accounts keys create sa-key.json` báo lỗi
`constraints/iam.disableServiceAccountKeyCreation`. Đây là policy ở organization level, account user không có quyền override.

**Giải pháp**: Chuyển sang **Workload Identity Federation (WIF)** — best practice của Google:
1. Tạo Workload Identity Pool + OIDC Provider cho GitHub Actions.
2. Bind service account `mlops-lab-sa` với GitHub repo qua attribute condition `assertion.repository_owner=='tnhoang462'`.
3. Workflow dùng `google-github-actions/auth@v2` thay vì JSON key trong secret.

Kết quả: 6 GitHub secrets thay vì 5 — `WIF_PROVIDER` và `WIF_SERVICE_ACCOUNT` thay cho `CLOUD_CREDENTIALS`. VM cũng dùng SA attached qua metadata server (không cần `sa-key.json` trên đĩa).

### 2.2 Eval gate chặn deploy ở lần chạy đầu (đúng thiết kế)
**Vấn đề**: Pipeline lần 1 với 2998 mẫu chỉ đạt `accuracy 0.684 < 0.70` → eval gate FAIL → deploy SKIPPED. Ban đầu tưởng là bug.

**Giải pháp**: Đây chính là behavior mong muốn của rubric Bước 2 (4đ "Eval gate"). Ở Bước 3 sau khi thêm dữ liệu, accuracy lên 0.748 → eval gate PASS → deploy thành công. Đây là demo hoàn hảo về giá trị của **continuous training**.

### 2.3 Conflict setuptools 82 với mlflow 2.13
**Vấn đề**: `pkg_resources` bị xóa khỏi setuptools >= 81 nhưng mlflow 2.13.0 vẫn import nó → ModuleNotFoundError.

**Giải pháp**: Thêm `pip install "setuptools<81"` trước khi cài `requirements.txt` ở cả CI và môi trường local.

### 2.4 Compute zone hết quota ở `asia-southeast1-a` và `-b`
**Vấn đề**: Tạo VM bị reject "does not have enough resources available".

**Giải pháp**: Loop qua các zone trong region cùng provider, thử `asia-southeast1-c` thành công.

### 2.5 GitHub Actions không trigger trên repo fork
**Vấn đề**: Push lần đầu không thấy run nào trên Actions tab.

**Giải pháp**: GitHub disable workflows mặc định trên fork để chống abuse. Bấm nút **"I understand my workflows, go ahead and enable them"** trên Actions tab → push tiếp → trigger thành công.

### 2.6 Path filter của workflow trigger
**Vấn đề**: Một số commit không trigger pipeline.

**Giải pháp**: Workflow trigger có `paths` filter — chỉ chạy khi sửa `data/**.dvc`, `src/**.py`, `params.yaml` hoặc `.github/workflows/**.yml`. Empty commit và commit chỉ sửa README không trigger. Đã thêm `.github/workflows/**.yml` vào path filter để khi sửa workflow thì cũng tự test.

---

## 3. Kết quả tổng hợp

### 3.1 Pipeline runs

| # | Trigger | Train | Eval | Deploy | accuracy |
|---|---|---|---|---|---|
| 1 | Bước 2 lần đầu (2998 mẫu) | ✅ | ❌ | ⏭ skipped | 0.684 |
| 2 | Bước 3 thêm data (5996 mẫu) | ✅ | ✅ | ✅ | 0.748 |
| 3 | Bonus features (multi-algo, report, rollback, drift) | ✅ | ✅ | ✅ | 0.754 |
| 4 | Bonus 1 DagsHub remote tracking | ✅ | ✅ | ✅ | 0.748 |

### 3.2 So sánh Bước 2 vs Bước 3

| Chỉ số | Bước 2 (2998 mẫu) | Bước 3 (5996 mẫu) | Δ |
|---|---|---|---|
| accuracy | 0.6840 | 0.7480 | **+6.40%** |
| f1_score | 0.6832 | 0.7472 | +6.40% |
| eval gate ≥ 0.70 | ❌ FAIL | ✅ PASS | unblocked deploy |

### 3.3 Bonus đã hoàn thành

| Bonus | Cách triển khai |
|---|---|
| **1** DagsHub remote tracking | Inject `MLFLOW_TRACKING_URI/USERNAME/PASSWORD` secrets vào job Train; mlflow tự đẩy lên DagsHub |
| **2** Multi-algorithm | `_MODEL_REGISTRY` trong `src/train.py` hỗ trợ `random_forest`, `gradient_boosting`, `logistic_regression`; `params.yaml` thêm `model_type` |
| **3** Auto report | `_write_report()` ghi confusion matrix + precision/recall/f1 cho từng lớp vào `outputs/report.txt`, upload làm artifact |
| **4** Rollback | Eval job tải `models/current/metrics.json` từ GCS, so sánh với accuracy mới; chỉ promote `latest/* → current/*` khi mới ≥ cũ |
| **5** Drift warning | `_check_label_drift()` cảnh báo khi class < 10%, ghi `label_distribution` vào `metrics.json` |

---

## 4. Bằng chứng nộp bài

| File trong `screenshots/` | Mục rubric |
|---|---|
| `01_actions_list.png` | Pipeline overview |
| `02_run1_eval_blocked_acc068.png` | Bước 2 — Eval gate (4đ) |
| `03_run2_buoc3_all_green.png` | Bước 3 — Continuous training (12đ) |
| `04_mlflow_ui_overview.png` | Bước 1 — MLflow ≥3 runs (12đ) |
| `05_mlflow_compare.png` | Bước 1 — Phân tích & so sánh (4đ) |
| `05b_mlflow_run_detail.png` | Bước 1 — Metrics chi tiết (8đ) |
| `06_run3_bonus_features.png` | All bonuses |
| `07_curl_endpoints.png` | Bước 2 — Serving (12đ) |
| `08_gcs_listing.png` | Bước 2 — DVC + GCS (12đ) |
| `09_bonus3_report.png` | Bonus 3 — Confusion matrix |

---

## 5. Tổng điểm dự kiến: 100/100

- Chính: 80/80 (8 mục)
- Bonus: 20/20 (5 bonuses)
