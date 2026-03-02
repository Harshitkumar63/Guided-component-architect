# Guided Component Architect

AI-powered system that generates Angular standalone components from natural-language descriptions using Groq LLM, with strict design-system enforcement and self-correcting validation.

---

## How It Works

1. You describe a component in plain English.
2. The LLM generates an Angular standalone component.
3. A deterministic validator checks the code against design-system rules (colors, syntax, structure).
4. If validation fails, the system automatically retries with error feedback (up to 2 retries).
5. The final validated component is printed to stdout.

---

## Setup

```bash
# Clone and enter project
cd guided-component-architect

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_groq_api_key_here
```

Get your free API key from [https://console.groq.com](https://console.groq.com).

---

## Usage

### Basic command

```bash
python main.py "A pricing card with three tiers"
```

### Interactive mode (prompts you for input)

```bash
python main.py
```

### Save output to a file

```bash
python main.py "A login card" > login-card.component.ts
```

---

## Example: Input and Output

### Input

```bash
python main.py "A pricing card with three tiers"
```

### Output (stderr logs + stdout component)

**Logs (stderr):**

```
------------------------------------------------------------
  Guided Component Architect - Generation Pipeline
------------------------------------------------------------

[13:02:22] INFO  Generation start: creating initial component.
[13:02:24] INFO  Initial generation complete.
[13:02:24] INFO  Running validation pass 1.
[13:02:24] INFO  Final success: component passed validation on first attempt.

------------------------------------------------------------
  FINAL ANGULAR COMPONENT
------------------------------------------------------------
```

**Generated Component (stdout):**

```typescript
import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-pricing-card',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="container">
      <div class="card" *ngFor="let tier of tiers">
        <div class="card-header">{{ tier.name }}</div>
        <div class="card-price">{{ tier.price }}</div>
        <ul>
          <li *ngFor="let feature of tier.features">{{ feature }}</li>
        </ul>
        <button class="btn" (click)="onSelect(tier)">Select</button>
      </div>
    </div>
  `,
  styles: [`
    :host { font-family: 'Inter', sans-serif; }
    .container { display: flex; gap: 16px; padding: 16px; }
    .card {
      background: #f1f5f9;
      border: 2px solid #6366f1;
      border-radius: 8px;
      padding: 16px;
      width: 250px;
    }
    .card-header {
      background: #6366f1;
      color: #f1f5f9;
      padding: 8px 16px;
      border-radius: 8px;
      font-weight: 600;
    }
    .btn {
      background: #6366f1;
      color: #f1f5f9;
      border: none;
      border-radius: 8px;
      padding: 8px 16px;
      cursor: pointer;
    }
  `]
})
export class PricingCardComponent {
  tiers: any[] = [
    { name: 'Basic', price: '$9/mo', features: ['Feature 1', 'Feature 2'] },
    { name: 'Pro', price: '$19/mo', features: ['Feature 1', 'Feature 2', 'Feature 3'] },
    { name: 'Enterprise', price: '$49/mo', features: ['All features'] }
  ];

  onSelect(tier: any): void {
    console.log('Selected:', tier.name);
  }
}
```

> **Note:** Only design-system colors (`#6366f1`, `#f1f5f9`) are allowed. Any other color causes validation failure and automatic retry.

---

## Run Tests

```bash
pytest -q
```

Tests cover color validation, syntax checking, structure validation, and demo mode — all without needing an API key.

---

## Project Structure

```
guided-component-architect/
main.py              - CLI entry point
agent_loop.py        - Generate > Validate > Retry loop
generator.py         - Groq API calls + prompt engineering
validator.py         - Deterministic design-system validator
logger.py            - Timestamped logging utility
design-system.json   - Immutable design tokens
requirements.txt     - Python dependencies
.env                 - API key (not committed)
tests/
  test_validator.py  - Validator unit tests
  test_demo_mode.py  - Demo mode tests
```

---

## Design System Tokens

Defined in `design-system.json`:

| Token           | Value     |
|-----------------|-----------|
| Primary Color   | `#6366f1` |
| Secondary Color | `#f1f5f9` |
| Border Radius   | `8px`     |
| Font Family     | `Inter`   |
| Spacing         | `16px`    |

---

## Tech Stack

- Python 3.10+
- Groq SDK + LLaMA 3.3 70B Versatile
- pytest for testing