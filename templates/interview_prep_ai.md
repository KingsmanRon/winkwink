# Interview Preparation: AI/ML Companies

## Company Types
- AI Research Labs: Anthropic, OpenAI, DeepMind, Cohere, Mistral
- AI Infrastructure: NVIDIA, Databricks, Anyscale, Modal
- AI Applications: Scale AI, Hugging Face, Character.ai, Perplexity

---

## Technical Preparation

### AI Infrastructure Core Concepts
- [ ] GPU cluster architecture (NVIDIA DGX, cloud GPU instances)
- [ ] Distributed training frameworks (Horovod, DeepSpeed, PyTorch DDP)
- [ ] Model serving patterns (TensorRT, Triton Inference Server, vLLM)
- [ ] Training job orchestration (Kubernetes, Slurm, Ray)
- [ ] Storage for ML (high-throughput for training data, model artifacts)
- [ ] Network fabric for distributed training (InfiniBand, NVLink, RoCE)

### MLOps & Platform Topics
- [ ] Feature stores (Feast, Tecton)
- [ ] Experiment tracking (MLflow, Weights & Biases)
- [ ] Model registries and versioning
- [ ] A/B testing infrastructure for models
- [ ] Model monitoring and drift detection
- [ ] Data versioning (DVC, LakeFS)
- [ ] Pipeline orchestration (Airflow, Kubeflow, Dagster)

### LLM-Specific Infrastructure
- [ ] Inference optimization (batching, KV caching, speculative decoding)
- [ ] Multi-GPU and multi-node serving
- [ ] Cost optimization for GPU workloads
- [ ] Fine-tuning infrastructure (LoRA, QLoRA)
- [ ] RAG system architecture
- [ ] Tokenization and prompt management
- [ ] Context length handling

---

## Sample Interview Questions

### System Design
1. "Design infrastructure to serve an LLM to 1 million concurrent users"
2. "How would you build a platform for researchers to run distributed training jobs?"
3. "Design a system for A/B testing different model versions in production"
4. "How do you handle GPU failures during a multi-day training run?"
5. "Design a feature store that serves both batch and real-time use cases"

### Technical Deep-Dives
1. "Explain how you would optimize inference costs while maintaining latency SLAs"
2. "Walk me through the process of deploying a new model version safely"
3. "How would you debug a training run that's not converging?"
4. "Design monitoring for an LLM-powered product"
5. "How do you handle model versioning and rollbacks?"

### Behavioral
1. "Tell me about a time you had to learn a new technology quickly"
2. "How do you balance research flexibility with production reliability?"
3. "Describe a situation where you had to make trade-offs between cost and performance"

---

## Transferable Skills to Highlight

### From Cloud Infrastructure Background
Your experience directly applies to AI infrastructure:

| Your Skill | AI Application |
|------------|----------------|
| Kubernetes | GPU cluster orchestration, job scheduling |
| Terraform/IaC | Reproducible ML environments |
| Multi-cloud | GPU availability across providers |
| Enterprise architecture | Scalable ML platforms |
| Security/compliance | Model access control, audit logging |
| Monitoring | Training job monitoring, model performance |
| CI/CD | MLOps pipelines, model deployment |
| Cost optimization | GPU cost management |

### Key Talking Points
- "My Kubernetes experience translates directly to GPU workload orchestration"
- "I've built self-service platforms, which is exactly what ML teams need"
- "Infrastructure as Code ensures reproducibility for experiments"
- "My multi-cloud expertise helps optimize GPU availability and cost"

---

## Questions You Should Ask

### Technical
- "What's your current GPU utilization rate and how do you optimize it?"
- "How do researchers request and get access to compute resources?"
- "What's the biggest infrastructure challenge you're facing right now?"
- "How do you balance research experimentation with production stability?"

### Team & Culture
- "How do infrastructure and research teams collaborate?"
- "What does the on-call rotation look like?"
- "How are infrastructure priorities decided?"

### Growth
- "What opportunities exist for learning more about ML?"
- "How do you support engineers transitioning into ML infrastructure?"
- "What does career growth look like for platform engineers?"

---

## Key Topics to Study

### GPU Infrastructure
- CUDA programming basics
- GPU memory hierarchy
- Multi-GPU communication (NVLink, PCIe)
- GPU scheduling in Kubernetes

### Distributed Training
- Data parallelism vs model parallelism
- Gradient synchronization strategies
- Checkpointing and fault tolerance
- Mixed precision training

### Model Serving
- Batching strategies
- Model quantization
- Inference optimization techniques
- Load balancing for ML workloads

---

## Resources for Further Study

### Courses
- "Full Stack Deep Learning" (course)
- "MLOps Zoomcamp" (free course)
- NVIDIA Deep Learning Institute

### Books
- "Designing Machine Learning Systems" by Chip Huyen
- "Machine Learning Engineering" by Andriy Burkov

### Blogs & Papers
- Anthropic Engineering Blog
- OpenAI Research Blog
- Google AI Blog
- MLOps Community resources

### Tools to Explore
- Ray (distributed computing)
- vLLM (LLM serving)
- Triton Inference Server
- MLflow
- Weights & Biases
