# AWS capacity and cost estimate

Estimate recorded 2026-07-16 for `ap-southeast-1` (Singapore). This is a planning
estimate, not an authorization to resize infrastructure. Recalculate in AWS Pricing
Calculator before purchase or Savings Plan commitment.

## Current shared environment

- EC2 `i-07af453b12aa01ff2`: `t3.small`, 2 vCPU, 2 GiB RAM.
- RDS PostgreSQL: `db.t4g.small`, 2 vCPU, 2 GiB RAM, shared by `rag_utils` and `brp`.
- EC2 schedule: 06:45–19:05 daily, approximately 370 instance-hours/month.
- RDS schedule: 06:30–19:15 daily, approximately 382.5 instance-hours/month.
- Neptune, S3, backups, logs and data transfer are unchanged and excluded from the
  comparison below.

The current EC2 is insufficient for the combined Hybrid-RAG and Rule Platform
workload when Joern runs. Joern is a JVM/CPG workload that may consume 8–16 GiB
while the existing services, Rule API/worker/UI, OS, Docker and page cache also
remain resident. T3 CPU-credit behavior is also a poor fit for sustained analysis.
No GPU is required.

## Recommended options

### Single-host pilot

- EC2 `m7i.2xlarge`: 8 vCPU, 32 GiB RAM, x86_64.
- 150 GB gp3 at the included 3,000 IOPS/125 MB/s baseline.
- RDS `db.t4g.medium`: 2 vCPU, 4 GiB RAM.
- Keep the office-hours schedules.

This is the simplest deployment but Joern can still contend with the application
services during a large analysis job.

### Preferred production topology

- Application EC2 `m7i.xlarge`: 4 vCPU, 16 GiB RAM.
- On-demand analysis worker `m7i.2xlarge`: 8 vCPU, 32 GiB RAM, started only for
  Joern/extraction windows.
- RDS at least `db.t4g.medium`; evaluate `db.m7g.large` and Multi-AZ from observed
  CPU, freeable memory, connections and latency when a production SLA applies.

Separating the analysis worker prevents source mining from degrading Hybrid-RAG or
the Rule API and can cost less when Joern runs infrequently.

## Monthly comparison

On-Demand planning rates used: `t3.small` $0.0264/h, `m7i.xlarge` $0.252/h,
`m7i.2xlarge` $0.504/h, RDS `db.t4g.small` $0.051/h, `db.t4g.medium` $0.102/h,
`db.m7g.large` $0.234/h and Singapore gp3 $0.096/GB-month. VND uses the indicative
rate 26,260 VND/USD. The current EBS comparison assumes 30 GB because the AWS
account used for development cannot read the live volume size.

| Scenario | Office-hours estimate | Approximate VND | Increase from current |
|---|---:|---:|---:|
| Current: `t3.small` + `db.t4g.small` + assumed 30 GB gp3 | $32.16/month | 0.85M | — |
| Single host, keep current RDS | $220.39/month | 5.79M | +$188.23 |
| Single host + `db.t4g.medium` | $239.90/month | 6.30M | +$207.74 |
| Single host + `db.m7g.large` Single-AZ | $290.39/month | 7.63M | +$258.23 |
| Split topology, 40 Joern hours and 200 GB total gp3 | $171.62/month | 4.51M | +$139.46 |

If the single-host recommendation runs 24/7, EC2 + `db.t4g.medium` + 150 GB gp3 is
approximately $456.78/month versus approximately $59.38/month for the current
comparison, an increase of about $397.40/month. Budget 10–15% above estimates for
snapshots, logs and data transfer. EBS is billed while EC2 is stopped.

References: [AWS general-purpose instance specifications](https://aws.amazon.com/ec2/instance-types/general-purpose/),
[AWS EBS gp3](https://aws.amazon.com/ebs/general-purpose/), and
[AWS RDS pricing](https://aws.amazon.com/rds/postgresql/pricing/).

