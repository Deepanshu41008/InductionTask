# -*- coding: utf-8 -*-
"""Untitled1.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/113lYC7bVVLph2qE-zIygf20vl0N4hnaw
"""

!pip install transformers datasets accelerate pandas torch

import pandas as pd
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments, DataCollatorForLanguageModeling
from datasets import Dataset

# Inference function
def generate_response(prompt):
    inputs = tokenizer.encode(prompt, return_tensors="pt").to(device)
    outputs = model.generate(
        inputs,
        max_length=200,
        do_sample=True,
        top_k=50,
        top_p=0.95,
        temperature=0.9
    )
    return tokenizer.decode(outputs[0], skip_special_tokens=True)

# Example usage
print(generate_response("Hello, how are you today?"))

# Load dataset
df = pd.read_parquet("hf://datasets/Cynaptics/persona-chat/data/train-00000-of-00001.parquet")

# Combine persona and dialogue into a single text field
df["combined_text"] = df.apply(lambda row: ' '.join(row["persona_b"]) + " " + ' '.join(row["dialogue"]), axis=1)
df = df.rename(columns={"combined_text": "text"})

# Convert DataFrame to Dataset object
dataset = Dataset.from_pandas(df[["text"]])
dataset = dataset.train_test_split(test_size=0.1)
train_dataset = dataset["train"]
eval_dataset = dataset["test"]

# Initialize model and tokenizer
model_name = "microsoft/DialoGPT-medium"
tokenizer = AutoTokenizer.from_pretrained(model_name)
tokenizer.pad_token = tokenizer.eos_token
model = AutoModelForCausalLM.from_pretrained(model_name)

# Define tokenization function
def tokenize_function(examples):
    return tokenizer(examples["text"], truncation=True, max_length=512)

# Tokenize datasets
train_dataset = train_dataset.map(tokenize_function, batched=True, remove_columns=["text"])
eval_dataset = eval_dataset.map(tokenize_function, batched=True, remove_columns=["text"])

# Create data collator
data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

# Reduce batch size and gradient accumulation steps based on GPU capability
batch_size = 1  # Starting with a lower batch size
gradient_accumulation_steps = 16  # Accumulate gradients to maintain effective batch size

# Define training arguments
training_args = TrainingArguments(
    output_dir="./persona_chatbot_output",  # Directory where the model will be saved
    evaluation_strategy="steps",
    eval_steps=1000,
    save_steps=1000,
    num_train_epochs=5,
    per_device_train_batch_size=batch_size,
    gradient_accumulation_steps=gradient_accumulation_steps,
    learning_rate=2e-5,
    max_grad_norm=1.0,
    fp16=True,  # Enable mixed precision training if supported by GPU
    logging_steps=50,
    weight_decay=0.01,
    warmup_steps=200,
    lr_scheduler_type="cosine",
    report_to="none"
)

# Clear GPU cache
torch.cuda.empty_cache()

# Initialize trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    data_collator=data_collator
)

# Start training
trainer.train()

# Evaluate the model
results = trainer.evaluate()
print(results)

# Save model and tokenizer
trainer.save_model("./persona_chatbot_model")
tokenizer.save_pretrained("./persona_chatbot_model")