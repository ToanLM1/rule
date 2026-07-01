# Khảo sát Vendor Rule Engine — So sánh tổng quan, Cách nạp dữ liệu khởi tạo & Khuyến nghị

**Mục đích:** Nghiên cứu sơ bộ cho track sinh PGM source trong tương lai (xác nhận hôm thứ Hai: *PGM source = source code; mỗi PGM map tới một màn hình / batch job / interface (IF)*). Trọng tâm: từng rule engine **nạp dữ liệu khởi tạo** ra sao, kèm so sánh tổng quan (license, deployment, giá, ưu/nhược) và khuyến nghị cuối.

> **"Dữ liệu khởi tạo" = (A) định nghĩa rule + (B) bảng tham chiếu/lookup.** Dữ liệu giao dịch runtime (C) được truyền theo từng request nên nằm ngoài phạm vi. Các vendor khác nhau chủ yếu ở cách tác giả & nạp A và B.

## 1. So sánh tổng quan

| Vendor | Open source? | Hình thức deploy | Mô hình giá | Cách nạp dữ liệu khởi tạo | Hợp tự động hóa* |
|---|---|---|---|---|---|
| **Drools (KIE)** | ✅ Apache 2.0 | Self-host / nhúng (Java) | Miễn phí; hỗ trợ trả phí qua subscription Red Hat | File DRL, decision table Excel, KieFileSystem/classpath; chèn fact lúc khởi động | Cao (Java) |
| **IBM ODM** | ❌ Thương mại | Self-host, OpenShift/K8s, z/OS, SaaS | License enterprise, theo báo giá, **rất cao** (processor/VPC) | GUI Decision Center, import rule project → deploy RuleApp | Thấp–TB |
| **Camunda 8 (DMN)** | ⚠️ Một phần — community Apache 2.0, nhưng **8.6+ chạy production cần license thương mại** | Self-managed / SaaS | Enterprise **$50k–$200k+/năm**; SaaS ~$65k/năm (500k bản ghi) | File DMN qua classpath hoặc **upload REST** | Cao (REST) |
| **Progress Corticon** | ❌ Thương mại | Self-host / nhúng (.js) | Theo báo giá (thương mại) | Import Excel → rulesheet → biên dịch `.eds` → deploy server | Trung bình |
| **GoRules / Zen** | ✅ MIT (engine) | **Nhúng / self-host / cloud** | Engine miễn phí; cloud/BRMS theo báo giá | File **JSON (JDM)**, JDM Editor, import/export `.json` | **Rất cao (JSON, đa ngôn ngữ)** |
| **DecisionRules.io** | ❌ Thương mại | **SaaS / private cloud / self-host (Docker·K8s, air-gapped)** | Free tier → subscription; self-host theo báo giá | **Push REST API**, lookup table hạng nhất | **Rất cao (API-first)** |

*\*Hợp tự động hóa = mức độ dễ để một hệ thống bên ngoài sinh & nạp rule một cách lập trình — liên quan trực tiếp tới pipeline PGM của ta.*

## 2. Chi tiết từng vendor (cách nạp dữ liệu khởi tạo + ưu/nhược)

### 2.1 Drools (KIE) — *chuẩn Java open-source*
- **Dữ liệu khởi tạo:** Rule dạng `.drl` hoặc **decision table Excel/CSV**; nạp qua `KieFileSystem`/classpath. Dữ liệu tham chiếu chèn vào working memory dưới dạng fact lúc khởi động, hoặc đọc từ DB.
- **✅ Ưu:** Miễn phí (Apache 2.0); trưởng thành, đã kiểm chứng; decision table Excel để người nghiệp vụ chỉnh; cộng đồng lớn; nhúng được vào mọi app JVM.
- **❌ Nhược:** Thiên Java; learning curve dốc (cú pháp DRL, RETE); công cụ UI (Business Central) nặng/kém bóng bẩy; seed dữ liệu tham chiếu phải tự làm.

### 2.2 IBM ODM — *hạng nặng enterprise*
- **Dữ liệu khởi tạo:** Soạn trong Decision Center / Rule Designer; import dạng archive rule project, deploy thành RuleApp; dữ liệu tham chiếu qua Business Object Model.
- **✅ Ưu:** Governance/versioning/audit/người nghiệp vụ soạn rule mạnh nhất; đã kiểm chứng ở quy mô enterprise rất lớn; nhiều đích deploy (kể cả z/OS).
- **❌ Nhược:** **Rất đắt** (theo báo giá, license theo processor); vận hành nặng; **kém phù hợp nhất cho việc seed bằng lập trình**; lock-in vendor.

### 2.3 Camunda 8 (DMN) — *chuẩn hóa, process + decision*
- **Dữ liệu khởi tạo:** Decision table DMN `.dmn`; deploy qua classpath lúc khởi động hoặc **endpoint REST** ("one-click deploy"); đánh giá qua REST/Java API.
- **✅ Ưu:** Chuẩn **DMN của OMG** (tính khả chuyển); REST/deploy động xuất sắc; kết hợp decision với điều phối process (BPMN); modeler tốt.
- **❌ Nhược:** License siết chặt — **8.6+ chạy production cần license thương mại**; giá enterprise cao; stack nặng hơn một rule engine thuần.

### 2.4 Progress Corticon — *model-driven, low-code*
- **Dữ liệu khởi tạo:** Vocabulary (mô hình dữ liệu) + **rulesheet import từ Excel** → Ruleflow → biên dịch thành Decision Service `.eds` deploy lên server.
- **✅ Ưu:** Không cần code, thân thiện analyst; kiểm tra rule mạnh (phát hiện xung đột/thiếu sót); artifact `.eds` tự chứa; Corticon.js chạy được trong browser/serverless.
- **❌ Nhược:** Thương mại (báo giá); cộng đồng nhỏ hơn Drools/Camunda; cách model-driven kém linh hoạt cho sinh rule hoàn toàn tự động.

### 2.5 GoRules / Zen — *hiện đại, JSON-native, đa ngôn ngữ*
- **Dữ liệu khởi tạo:** **JSON Decision Model (JDM)** — đồ thị quyết định lưu dưới dạng JSON khả chuyển; soạn trong JDM Editor open-source; Zen engine nạp trực tiếp; import/export `.json` gọn gàng.
- **✅ Ưu:** **Engine MIT open-source & self-host miễn phí (đánh giá không giới hạn)**; định dạng JSON lý tưởng cho sinh rule bằng lập trình; **đa ngôn ngữ** (Rust/Node/Python/Go/Java/C#/Swift); nhúng hoặc cloud; thân thiện Git.
- **❌ Nhược:** Hệ sinh thái non/nhỏ hơn IBM/Drools; giá tier cloud/BRMS không công khai; ít công cụ governance enterprise sẵn có.

### 2.6 DecisionRules.io — *SaaS / self-host API-first*
- **Dữ liệu khởi tạo:** Decision table/tree quản lý qua **push REST API**; **lookup table** hạng nhất cho dữ liệu tham chiếu (có cache).
- **✅ Ưu:** **API-first** (dễ tích hợp nhất với pipeline sinh rule tự động); deploy linh hoạt (SaaS / private cloud / self-host kể cả air-gapped); free tier để bắt đầu; UI cho người không phải dev.
- **❌ Nhược:** Thương mại (subscription / self-host báo giá); vendor mới; cần cân nhắc data-residency khi dùng SaaS cho viễn thông; độ trưởng thành hệ sinh thái thấp hơn các tên tuổi lớn.

## 3. Lăng kính ra quyết định cho use case của ta

Hệ thống của ta đã trích xuất tri thức nghiệp vụ có cấu trúc vào graph. Track PGM tương lai cần biến nó thành rule và **nạp tự động**. Vậy các yếu tố quyết định:
1. **Import bằng lập trình** (push được rule sinh ra mà không thao tác GUI?) → ưu thế: GoRules (JSON), DecisionRules (REST), Camunda (REST).
2. **Open source / kiểm soát chi phí** giai đoạn nghiên cứu/PoC → ưu thế: Drools, GoRules.
3. **Phù hợp deployment** (khả năng AWS, có thể air-gapped cho viễn thông HQ) → ưu thế các option self-host: Drools, GoRules, DecisionRules self-host, Camunda self-managed.
4. **Xử lý tiếng Hàn & governance enterprise** nếu lên production → IBM ODM mạnh nhất nhưng đắt.

## 4. Khuyến nghị

**Khuyến nghị số 1: GoRules (Zen / JDM) cho giai đoạn PoC.**
- Open source (MIT), self-host miễn phí, đa ngôn ngữ, và **định dạng JSON (JDM) hợp nhất cho hệ thống tự sinh rule** từ tri thức trích xuất. Chi phí & ma sát thấp nhất để kiểm chứng pipeline "tri thức → rule → nạp".

**Lựa chọn thay thế mạnh (API-first): DecisionRules.io.**
- Nếu muốn một BRMS managed/low-code với chỉnh rule cho người không phải dev và **nạp qua REST**, đây là option API-first sạch nhất, có self-host cho nhu cầu data-residency viễn thông.

**Phương án enterprise an toàn: Drools.**
- Nếu khách muốn một engine open-source hoàn toàn, native Java đã kiểm chứng, decision table chỉnh bằng Excel, không lock-in vendor, thì Drools là lựa chọn bảo thủ (đổi lại tốn công kỹ thuật nội bộ hơn).

**Chỉ cân nhắc nếu khách yêu cầu rõ: IBM ODM / Camunda.**
- **IBM ODM** — chỉ chọn khi governance/audit enterprise và hệ thống IBM sẵn có vượt trội hơn chi phí cao và độ hợp tự động hóa thấp.
- **Camunda** — chọn khi cần thêm điều phối process BPMN bên cạnh quyết định DMN; nếu không, license bị siết khiến nó kém hấp dẫn cho nhu cầu rule engine thuần.

> **Bước tiếp theo đề xuất:** Prototype đường nạp trên **GoRules (JSON) + một option API-first (DecisionRules)** — sinh một bộ rule nhỏ từ tri thức trích xuất, nạp vào, và đánh giá. Việc này kiểm chứng tính khả thi trước giai đoạn thiết kế PGM chuyên biệt, với chi phí license gần như bằng 0.

---

**Nguồn:** Tài liệu Drools; giá & decision table IBM ODM; giá Camunda, cập nhật license 8.6, deploy DMN; Progress Corticon & tài liệu deployment; GoRules Zen (GitHub), giá, JDM; giá self-hosted/cloud DecisionRules.
