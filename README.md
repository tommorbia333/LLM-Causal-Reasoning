LLM Causal Reasoning Evaluation

This project investigates how large language models represent causal and temporal structure in narratives, and compares their behavior to human participants.

Overview
Built a jsPsych experiment to collect human judgments on narrative understanding
Developed a pipeline to run LLMs (e.g., Qwen 2.5 7B) on the same stories incrementally
Extracted model representations and constructed event graphs
Compared model-generated graphs to human and gold-standard structures
Methods
Transformer models (Qwen, GPT variants)
Embedding extraction and hidden state analysis
Representational geometry (RSA / distance-based comparisons)
Behavioral evaluation (human vs model responses)
Tech Stack

Python, PyTorch, jsPsych, HuggingFace, data visualization tools

Status

Work in progress — part of MSc dissertation at UCL
