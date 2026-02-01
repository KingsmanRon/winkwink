# Interview Preparation: Quant/Trading Companies

## Company Types
- Quant Trading: Jane Street, Two Sigma, Citadel, DE Shaw, Jump Trading
- Market Makers: Optiver, IMC, Virtu Financial
- Crypto Trading: Alameda (historical), trading desks at major exchanges

---

## Technical Preparation

### System Design Focus Areas
- [ ] Low-latency architecture patterns (sub-millisecond requirements)
- [ ] High-throughput data pipelines (millions of events/sec)
- [ ] Disaster recovery with near-zero RPO/RTO
- [ ] Multi-region active-active deployments
- [ ] Network optimization and colocation strategies
- [ ] Time synchronization (NTP, PTP) for trading systems

### Quant-Specific Infrastructure Topics
- [ ] Time-series databases (InfluxDB, TimescaleDB, kdb+)
- [ ] Message queues for trading (Kafka, Chronicle Queue, Aeron)
- [ ] Deterministic systems and avoiding GC pauses
- [ ] Market data feed handling and normalization
- [ ] FIX protocol and market connectivity
- [ ] Order management systems (OMS)
- [ ] Regulatory compliance (SOC2, audit logging)

### Low-Latency Essentials
- [ ] Kernel bypass networking (DPDK, RDMA)
- [ ] Memory management and cache optimization
- [ ] Lock-free data structures
- [ ] CPU affinity and NUMA awareness
- [ ] Avoiding system calls in hot paths
- [ ] Profiling and benchmarking tools

---

## Sample Interview Questions

### System Design
1. "Design a system that can process 10 million market events per second with <1ms latency"
2. "How would you ensure exactly-once processing in a distributed trading system?"
3. "Design the infrastructure for deploying ML models that make trading decisions"
4. "How do you handle secrets management and access control for sensitive trading systems?"
5. "Design a market data distribution system that serves 1000 trading strategies"

### Technical Deep-Dives
1. "Walk me through how you would debug a latency spike in a trading system"
2. "How would you design a system for backtesting trading strategies at scale?"
3. "Explain the trade-offs between consistency and availability in a trading context"
4. "How do you handle clock synchronization across a distributed trading system?"
5. "Design a monitoring system that can detect anomalies in real-time trading"

### Behavioral
1. "Tell me about a time you had to make a critical decision under time pressure"
2. "How do you handle situations where system reliability conflicts with feature velocity?"
3. "Describe a complex incident you managed and what you learned"

---

## Compliance & Security Topics

### Regulatory Framework
- [ ] PCI-DSS compliance for payment systems
- [ ] SOC2 Type II audit requirements
- [ ] Data residency and GDPR considerations
- [ ] Encryption at rest and in transit standards
- [ ] Audit logging and immutable records
- [ ] Access control and least privilege

### Financial Services Security
- [ ] Network segmentation for trading systems
- [ ] Key management for encryption
- [ ] Identity and access management (IAM)
- [ ] Vulnerability management
- [ ] Incident response procedures

---

## Questions You Should Ask

### Technical
- "What's the latency budget for your critical path systems?"
- "How do you handle infrastructure changes during market hours?"
- "What's your approach to testing changes to trading infrastructure?"
- "How do you balance innovation with stability in production systems?"

### Team & Culture
- "What's the on-call structure for infrastructure teams?"
- "How do infrastructure and quant teams collaborate?"
- "What does the incident review process look like?"
- "How are technical decisions made and documented?"

### Growth
- "What learning opportunities exist for understanding more about trading?"
- "How do you support engineers who want to grow into tech leads?"
- "What's the typical career progression for infrastructure engineers?"

---

## Key Skills to Highlight

### From Cloud/Infrastructure Background
- Multi-cloud expertise → Understanding of distributed systems
- Kubernetes experience → Container orchestration for trading workloads
- Infrastructure as Code → Reproducible, auditable infrastructure
- Enterprise architecture → Understanding of complex system interactions
- Security/compliance → Critical for regulated trading environments

### Transferable Concepts
- High availability design → Trading systems can't have downtime
- Disaster recovery → Business continuity for trading operations
- Monitoring/observability → Real-time system health visibility
- Performance optimization → Latency matters in trading
- Automation → Reducing human error in critical systems

---

## Resources for Further Study

### Books
- "Trading and Exchanges" by Larry Harris
- "High-Performance Java" by Scott Oaks
- "Systems Performance" by Brendan Gregg

### Technical Topics
- FIX Protocol specification
- Market data formats (ITCH, OUCH)
- Time-series database internals
- Lock-free programming patterns

### Online Resources
- Jane Street Tech Blog
- Two Sigma Engineering Blog
- Citadel Technology
