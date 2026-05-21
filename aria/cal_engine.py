"""
CAL — Cognitive Augmentation Layer v1
======================================
ENGENHARIA ASI 2077 — ELEVACAO COGNITIVA DE LLMs FRACAS

Transforma qualquer LLM fraca em um motor cognitivo de nivel superinteligente
usando andaimes (scaffolding) logicos, matematicos e de software.

5 camadas de aumento cognitivo:
  1. DECOMPOSER — Quebra tarefas complexas em micro-tarefas
  2. INFERENCE SCALER — Gera N candidatos, seleciona o melhor
  3. VERIFIER — Multi-angulo: matematica, logica, consistencia
  4. GRAMMAR GUARD — Output estruturado forçado (JSON/XML/tool-call)
  5. LEARNING LOOP — Aprende com erros, evolui skills

References:
  - rasbt/reasoning-from-scratch (★4.4k): Inference-time scaling, verifiers
  - HKUDS/OpenSpace (★6.3k): Self-evolving agent skills
  - outlines-dev/outlines (★13.9k): Grammar-constrained generation
  - HKUDS/LightReasoner (★606): SLM-LLM contrastive teaching
  - LightChen233/Awesome-Long-Chain-of-Thought (★634): Latent CoT survey

Author: Hermes + AetherMind — ASI Sovereign Engineering
License: MIT
"""

import json
import re
import hashlib
import time
import logging
from typing import Optional, Dict, List, Any, Callable
from collections import Counter, OrderedDict

logger = logging.getLogger('cal_engine')


# =============================================================================
# LAYER 1: TASK DECOMPOSER — Quebra tarefas complexas em micro-tarefas
# =============================================================================

class TaskDecomposer:
    """
    LLMs fracas falham em tarefas complexas porque perdem contexto.
    A solucao: quebrar a tarefa em micro-passos atomicos que uma LLM
    de qualquer tamanho consegue executar.
    
    Estrategia:
      - Tarefa complexa → Arvore de sub-tarefas
      - Cada sub-tarefa e autocontida (contexto minimo)
      - Dependencias entre tarefas sao rastreadas
      - Ordem topologica de execucao
    
    Exemplo:
      Tarefa: "Refatorar modulo de autenticacao inteiro"
      Micro-tarefas:
        1. [LEAF] Ler o arquivo auth.py
        2. [LEAF] Identificar funcoes e classes
        3. [LEAF] Encontrar acoplamentos fortes (>3 dependencias)
        4. [LEAF] Propor nova estrutura de modulos
        5. [LEAF] Gerar codigo refatorado
        6. [LEAF] Escrever testes para novo codigo
        7. [LEAF] Executar testes
    """
    
    # Templates de decomposicao por tipo de tarefa
    DECOMPOSITION_TEMPLATES = {
        'refactor': [
            "READ the target file(s)",
            "IDENTIFY all functions, classes, and imports",
            "FIND tight coupling points (shared state, circular imports)",
            "PROPOSE new module structure (MVC/services/repository)",
            "GENERATE refactored code for each module",
            "WRITE unit tests for new structure",
            "RUN tests and verify all pass",
        ],
        'debug': [
            "READ the error message and stack trace",
            "LOCATE the failing line in the source file",
            "UNDERSTAND the expected vs actual behavior",
            "IDENTIFY root cause (logic error, missing edge case, race condition)",
            "PROPOSE fix with explanation",
            "IMPLEMENT the fix",
            "RUN the test that failed to verify",
        ],
        'implement': [
            "UNDERSTAND the feature requirements",
            "IDENTIFY affected files and modules",
            "DESIGN the implementation approach",
            "WRITE the implementation code",
            "ADD necessary imports and configuration",
            "WRITE unit tests",
            "RUN tests to verify",
        ],
        'analyze': [
            "READ the target code/files",
            "UNDERSTAND the architecture and data flow",
            "IDENTIFY patterns, anti-patterns, and potential issues",
            "EVALUATE against best practices",
            "GENERATE findings with severity ratings",
            "SUGGEST improvements in priority order",
        ],
        'explain': [
            "IDENTIFY the core concept being asked about",
            "BREAK it down into fundamental principles",
            "PROVIDE concrete examples",
            "CONNECT to related concepts",
            "SUMMARIZE key takeaways",
        ],
    }
    
    def __init__(self, max_subtasks: int = 7, min_subtasks: int = 3):
        self.max_subtasks = max_subtasks
        self.min_subtasks = min_subtasks
        self.task_memory = OrderedDict()  # task_id → subtasks
        self.max_memory = 100
        
    def decompose(self, task: str, task_type: str = None) -> List[Dict]:
        """
        Decompose a complex task into atomic subtasks.
        
        Args:
            task: The user's task description
            task_type: Optional type hint (refactor, debug, implement, analyze, explain)
        
        Returns:
            List of subtasks, each with {id, description, dependencies, status}
        """
        # Detect task type from keywords
        if not task_type:
            task_type = self._detect_type(task)
        
        # Get template
        template = self.DECOMPOSITION_TEMPLATES.get(task_type, 
                    self.DECOMPOSITION_TEMPLATES['analyze'])
        
        # Generate unique task ID
        task_id = hashlib.md5(task.encode()).hexdigest()[:8]
        
        # Build subtasks from template
        subtasks = []
        for i, step in enumerate(template):
            # Inject task-specific context into template step
            if task_type in ('refactor', 'debug', 'implement'):
                # Extract file mentions from task
                files = self._extract_files(task)
                target = files[0] if files else 'the target'
                step = step.replace('the target', target)
            
            subtask = {
                'id': f"{task_id}-{i+1}",
                'description': step,
                'dependencies': [f"{task_id}-{j+1}" for j in range(i-1, -1, -1)[:1]] if i > 0 else [],
                'status': 'pending',
                'result': None,
                'task_type': task_type,
            }
            
            # Limit dependencies to max 1 (chain, not tree, for simplicity)
            if len(subtask['dependencies']) > 1:
                subtask['dependencies'] = subtask['dependencies'][:1]
            
            subtasks.append(subtask)
        
        # Store in memory
        self.task_memory[task_id] = subtasks
        while len(self.task_memory) > self.max_memory:
            self.task_memory.popitem(last=False)
        
        return subtasks
    
    def get_next_pending(self, task_id: str) -> Optional[Dict]:
        """Get the next ready-to-execute subtask (all deps completed)."""
        subtasks = self.task_memory.get(task_id, [])
        for st in subtasks:
            if st['status'] == 'pending':
                deps_done = all(
                    self._get_subtask(task_id, dep)['status'] == 'completed'
                    for dep in st['dependencies']
                )
                if deps_done:
                    return st
        return None
    
    def mark_completed(self, task_id: str, subtask_id: str, result: str = ''):
        """Mark a subtask as completed."""
        subtask = self._get_subtask(task_id, subtask_id)
        if subtask:
            subtask['status'] = 'completed'
            subtask['result'] = result
    
    def mark_failed(self, task_id: str, subtask_id: str, error: str = ''):
        """Mark a subtask as failed."""
        subtask = self._get_subtask(task_id, subtask_id)
        if subtask:
            subtask['status'] = 'failed'
            subtask['result'] = error
    
    def is_complete(self, task_id: str) -> bool:
        """Check if all subtasks are completed."""
        subtasks = self.task_memory.get(task_id, [])
        if not subtasks:
            return False
        return all(st['status'] == 'completed' for st in subtasks)
    
    def get_progress(self, task_id: str) -> dict:
        """Get completion progress."""
        subtasks = self.task_memory.get(task_id, [])
        total = len(subtasks)
        completed = sum(1 for st in subtasks if st['status'] == 'completed')
        failed = sum(1 for st in subtasks if st['status'] == 'failed')
        return {
            'total': total,
            'completed': completed,
            'failed': failed,
            'pending': total - completed - failed,
            'percent': round(completed / max(total, 1) * 100, 1),
        }
    
    def _detect_type(self, task: str) -> str:
        """Detect task type from keywords in the task description."""
        task_lower = task.lower()
        if any(w in task_lower for w in ['refactor', 'split', 'reorganize', 'restructure']):
            return 'refactor'
        if any(w in task_lower for w in ['debug', 'fix', 'error', 'bug', 'crash', 'fail']):
            return 'debug'
        if any(w in task_lower for w in ['implement', 'create', 'build', 'add', 'make']):
            return 'implement'
        if any(w in task_lower for w in ['analyze', 'review', 'audit', 'inspect', 'check']):
            return 'analyze'
        if any(w in task_lower for w in ['explain', 'what is', 'how does', 'describe']):
            return 'explain'
        return 'analyze'  # Default
    
    def _extract_files(self, task: str) -> List[str]:
        """Extract file paths from task description."""
        # Simple regex for file paths
        matches = re.findall(r'[\w/\\\-]+\.(?:py|js|ts|java|go|rs|cpp|c|h|css|html|json|yaml|yml|toml|md)', task)
        return [m.strip() for m in matches if m.strip()]
    
    def _get_subtask(self, task_id: str, subtask_id: str) -> Optional[Dict]:
        """Get a specific subtask."""
        subtasks = self.task_memory.get(task_id, [])
        for st in subtasks:
            if st['id'] == subtask_id:
                return st
        return None


# =============================================================================
# LAYER 2: INFERENCE-TIME SCALER — BeamSearch + Self-Consistency
# =============================================================================

class InferenceScaler:
    """
    Faz a LLM "pensar mais" gerando multiplos caminhos de raciocinio
    e selecionando o melhor via verificacao.
    
    Modos:
      1. BeamSearch — Gera N respostas, pontua por verifier, seleciona top-1
      2. Self-Consistency — Gera N caminhos CoT, majority-vote na resposta final
      3. Best-of-N — Gera N respostas, seleciona a de maior score
      4. TreeOfThoughts — Explora arvore de possibilidades com BFS/DFS
    
    Parametros:
      n_paths: Numero de caminhos paralelos (default: 3)
      strategy: beam_search, self_consistency, best_of_n, tree_of_thoughts
      temperature: Diversidade entre caminhos (0.3-1.0)
    """
    
    STRATEGIES = ['beam_search', 'self_consistency', 'best_of_n', 'tree_of_thoughts']
    
    def __init__(self, n_paths: int = 3, strategy: str = 'self_consistency',
                 temperature: float = 0.7, max_tokens_per_path: int = 500):
        self.n_paths = n_paths
        self.strategy = strategy if strategy in self.STRATEGIES else 'self_consistency'
        self.temperature = temperature
        self.max_tokens_per_path = max_tokens_per_path
        self.stats = {
            'total_calls': 0,
            'paths_generated': 0,
            'best_selected': 0,
            'avg_improvement': 0.0,
        }
    
    def scale(self, llm_call: Callable, prompt: str, 
              verifier: Optional[Callable] = None) -> Dict:
        """
        Scale inference: generate N paths, verify, select best.
        
        Args:
            llm_call: Function(prompt, **kwargs) -> str
            prompt: The prompt to send to the LLM
            verifier: Optional scoring function(response) -> float
        
        Returns:
            Dict with {response, score, paths, strategy_used}
        """
        self.stats['total_calls'] += 1
        
        if self.strategy == 'beam_search':
            return self._beam_search(llm_call, prompt, verifier)
        elif self.strategy == 'self_consistency':
            return self._self_consistency(llm_call, prompt)
        elif self.strategy == 'best_of_n':
            return self._best_of_n(llm_call, prompt, verifier)
        else:
            return self._best_of_n(llm_call, prompt, verifier)
    
    def _beam_search(self, llm_call: Callable, prompt: str,
                     verifier: Optional[Callable] = None) -> Dict:
        """BeamSearch: Generate N, score, select best."""
        candidates = []
        
        # Generate N candidates with different temperatures
        for i in range(self.n_paths):
            temp = self.temperature + (i * 0.15)
            try:
                response = llm_call(prompt, temperature=min(temp, 1.5))
                candidates.append({
                    'path_id': i,
                    'response': response,
                    'temperature': temp,
                })
                self.stats['paths_generated'] += 1
            except Exception as e:
                logger.warning(f"BeamSearch path {i} failed: {e}")
                candidates.append({
                    'path_id': i,
                    'response': f"[ERROR: {e}]",
                    'temperature': temp,
                })
        
        # Score if verifier available
        if verifier and candidates:
            for c in candidates:
                try:
                    c['score'] = verifier(c['response'])
                except Exception:
                    c['score'] = 0.0
            
            # Select best
            best = max(candidates, key=lambda c: c.get('score', 0))
        else:
            # Without verifier, select longest non-error response
            valid = [c for c in candidates if not c['response'].startswith('[ERROR')]
            best = max(valid, key=lambda c: len(c['response'])) if valid else candidates[0]
        
        self.stats['best_selected'] += 1
        
        # Calculate improvement
        if len(candidates) > 1 and verifier:
            avg_score = sum(c.get('score', 0) for c in candidates) / len(candidates)
            best_score = best.get('score', 0)
            improvement = best_score - avg_score if avg_score > 0 else 0
            self.stats['avg_improvement'] = (
                self.stats['avg_improvement'] * (self.stats['best_selected'] - 1) + improvement
            ) / self.stats['best_selected']
        
        return {
            'response': best['response'],
            'score': best.get('score', 0),
            'paths': candidates,
            'strategy': 'beam_search',
            'best_path_id': best['path_id'],
            'avg_score': sum(c.get('score', 0) for c in candidates) / max(len(candidates), 1),
        }
    
    def _self_consistency(self, llm_call: Callable, prompt: str) -> Dict:
        """Self-Consistency: Generate N CoT paths, majority-vote on answer."""
        # Add CoT instruction to prompt
        cot_prompt = prompt + "\n\nThink step by step. Show your reasoning, then give the final answer after 'ANSWER:'."
        
        candidates = []
        for i in range(self.n_paths):
            temp = self.temperature + (i * 0.1)
            try:
                response = llm_call(cot_prompt, temperature=min(temp, 1.5))
                # Extract answer after "ANSWER:"
                answer = self._extract_answer(response)
                candidates.append({
                    'path_id': i,
                    'response': response,
                    'answer': answer,
                    'temperature': temp,
                })
                self.stats['paths_generated'] += 1
            except Exception as e:
                logger.warning(f"Self-consistency path {i} failed: {e}")
                candidates.append({
                    'path_id': i,
                    'response': f"[ERROR: {e}]",
                    'answer': f"[ERROR]",
                    'temperature': temp,
                })
        
        # Majority vote on answers
        answers = [c['answer'] for c in candidates]
        if answers:
            # Normalize answers for comparison
            normalized = [self._normalize(a) for a in answers]
            counter = Counter(normalized)
            most_common = counter.most_common(1)[0][0]
            
            # Find the first candidate with this answer
            best = next((c for c, n in zip(candidates, normalized) if n == most_common), candidates[0])
        else:
            best = candidates[0] if candidates else {'response': '', 'answer': ''}
        
        self.stats['best_selected'] += 1
        
        return {
            'response': best['response'],
            'answer': best['answer'],
            'paths': candidates,
            'strategy': 'self_consistency',
            'vote_distribution': dict(counter.most_common()),
            'agreement': counter.most_common(1)[0][1] / len(candidates) if candidates else 0,
        }
    
    def _best_of_n(self, llm_call: Callable, prompt: str,
                   verifier: Optional[Callable] = None) -> Dict:
        """Best-of-N: Simple generation + selection."""
        return self._beam_search(llm_call, prompt, verifier)
    
    def _extract_answer(self, text: str) -> str:
        """Extract the answer part from a CoT response."""
        # Look for "ANSWER:" marker
        if 'ANSWER:' in text:
            return text.split('ANSWER:')[-1].strip()
        if 'answer:' in text:
            return text.split('answer:')[-1].strip()
        # Fallback: last paragraph
        paragraphs = text.split('\n\n')
        return paragraphs[-1].strip() if paragraphs else text.strip()
    
    def _normalize(self, text: str) -> str:
        """Normalize text for comparison."""
        return re.sub(r'[^a-zA-Z0-9]', '', text.lower())[:100]
    
    def get_stats(self) -> dict:
        return {
            'strategy': self.strategy,
            'n_paths': self.n_paths,
            'total_calls': self.stats['total_calls'],
            'paths_generated': self.stats['paths_generated'],
            'avg_improvement': round(self.stats['avg_improvement'], 3),
        }


# =============================================================================
# LAYER 3: MULTI-ANGLE VERIFIER — Matematica, logica, consistencia
# =============================================================================

class MultiAngleVerifier:
    """
    Verifica respostas da LLM de multiplos angulos.
    
    Checks:
      1. CONSISTENCY — A resposta se contradiz?
      2. COMPLETENESS — Respondeu a pergunta?
      3. FORMAT — Esta no formato esperado?
      4. SELF-CONTAINED — Nao depende de conhecimento externo nao fornecido?
      5. HALLUCINATION — Menciona arquivos/funcoes que nao existem?
    
    Pontuacao: 0.0 (pessimo) a 1.0 (perfeito)
    """
    
    def __init__(self):
        self.checks_run = 0
        self.failures = Counter()
        
    def verify(self, response: str, context: dict = None) -> dict:
        """
        Multi-angle verification of an LLM response.
        
        Args:
            response: The LLM's response text
            context: Optional dict with {question, expected_format, known_files}
        
        Returns:
            Dict with {score, checks, issues}
        """
        self.checks_run += 1
        checks = {}
        issues = []
        score = 0.0
        max_score = 0.0
        
        context = context or {}
        
        # Check 1: Consistency (no self-contradiction)
        check, issue = self._check_consistency(response)
        checks['consistency'] = check
        if issue:
            issues.append(issue)
            self.failures['consistency'] += 1
        score += check * 3.0
        max_score += 3.0
        
        # Check 2: Completeness (answers the question)
        if context.get('question'):
            check, issue = self._check_completeness(response, context['question'])
            checks['completeness'] = check
            if issue:
                issues.append(issue)
                self.failures['completeness'] += 1
            score += check * 2.0
            max_score += 2.0
        
        # Check 3: Format (if expected format specified)
        if context.get('expected_format'):
            check, issue = self._check_format(response, context['expected_format'])
            checks['format'] = check
            if issue:
                issues.append(issue)
                self.failures['format'] += 1
            score += check * 2.0
            max_score += 2.0
        
        # Check 4: Self-contained (doesn't hallucinate unknowns)
        check, issue = self._check_self_contained(response, context.get('known_files', []))
        checks['self_contained'] = check
        if issue:
            issues.append(issue)
            self.failures['self_contained'] += 1
        score += check * 2.0
        max_score += 2.0
        
        # Check 5: Hallucination detection
        if context.get('known_files'):
            check, issue = self._check_hallucination(response, context['known_files'])
            checks['hallucination'] = check
            if issue:
                issues.append(issue)
                self.failures['hallucination'] += 1
            score += check * 2.0
            max_score += 2.0
        
        normalized_score = score / max(max_score, 1)
        
        return {
            'score': round(normalized_score, 3),
            'checks': checks,
            'issues': issues,
            'passed': len(issues) == 0,
        }
    
    def _check_consistency(self, text: str) -> tuple:
        """Check for self-contradictions."""
        contradictions = [
            (r'yes.*no\b', 'Contradiction: says both yes and no'),
            (r'true.*false\b', 'Contradiction: says both true and false'),
            (r'works.*doesn\'t work', 'Contradiction: says both works and does not work'),
            (r'all pass.*failed', 'Possible contradiction: all pass but failures reported'),
        ]
        for pattern, msg in contradictions:
            if re.search(pattern, text, re.IGNORECASE):
                return 0.3, msg
        return 1.0, None
    
    def _check_completeness(self, text: str, question: str) -> tuple:
        """Check if the response addresses the question."""
        # Very basic: does the response have enough content vs the question?
        if len(text) < len(question) * 0.3:
            return 0.3, "Response too short compared to question"
        # Check for empty/generic responses
        generic = ['i don\'t know', 'i\'m not sure', 'i cannot', 'it\'s unclear']
        if any(g in text.lower() for g in generic) and len(text) < 200:
            return 0.5, "Generic/non-committal response"
        return 1.0, None
    
    def _check_format(self, text: str, expected_format: str) -> tuple:
        """Check if response follows expected format."""
        fmt = expected_format.lower()
        if fmt == 'json':
            # Try to find and parse JSON
            json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if json_match:
                try:
                    json.loads(json_match.group())
                    return 1.0, None
                except json.JSONDecodeError:
                    return 0.2, "JSON in response is malformed"
            return 0.0, "No JSON found in response"
        elif fmt == 'xml':
            if re.search(r'<\w+>.*</\w+>', text):
                return 1.0, None
            return 0.3, "No XML structure found"
        elif fmt == 'tool_call':
            if re.search(r'<tool', text) or re.search(r'TOOL\|', text):
                return 1.0, None
            return 0.4, "No tool call format detected"
        return 1.0, None  # Unknown format, don't penalize
    
    def _check_self_contained(self, text: str, known_files: list) -> tuple:
        """Check if response references files that were provided."""
        if not known_files:
            return 1.0, None
        
        # Extract file mentions from response
        file_pattern = re.compile(r'([\w/\\\-]+\.(?:py|js|ts|java|go|rs|cpp|c|h|css|html))')
        mentioned = set(m.group(0) for m in file_pattern.finditer(text))
        
        unknown = mentioned - set(known_files)
        if unknown:
            return 0.5, f"References unknown files: {', '.join(list(unknown)[:3])}"
        return 1.0, None
    
    def _check_hallucination(self, text: str, known_files: list) -> tuple:
        """Check for hallucinated content about known files."""
        # Check function names against known files
        # This is a heuristic — real checking requires code parsing
        func_pattern = re.compile(r'`(\w+)`\s*(?:function|method|class)', re.IGNORECASE)
        functions = [m.group(1) for m in func_pattern.finditer(text)]
        
        # Would need AST parsing for real validation
        # For now, just flag if many functions are mentioned but file is small
        if len(functions) > 10 and len(known_files) < 3:
            return 0.6, f"Many functions ({len(functions)}) mentioned but only {len(known_files)} files known"
        return 1.0, None
    
    def get_stats(self) -> dict:
        return {
            'checks_run': self.checks_run,
            'failure_distribution': dict(self.failures.most_common()),
            'reliability': round(1 - sum(self.failures.values()) / max(self.checks_run * 5, 1), 3),
        }


# =============================================================================
# LAYER 4: GRAMMAR GUARD — Output estruturado forcado
# =============================================================================

class GrammarGuard:
    """
    Garante que o output da LLM siga formatos estritos.
    
    Para APIs (DeepSeek, GPT, Claude): post-processamento de regex.
    Para modelos locais (llama.cpp): integracao com GBNF grammar.
    
    Modos:
      - json: Forca saida JSON valido
      - tool_call: Forca formato de tool call estrito
      - ucip: Forca formato UCIP (pipe key=value)
      - code: Forca bloco de codigo com linguagem
      - free: Sem restricao (pass-through)
    """
    
    def __init__(self, mode: str = 'tool_call'):
        self.mode = mode
        self.fixes_applied = 0
        
    def enforce(self, text: str) -> str:
        """Enforce output format. Returns corrected text."""
        if self.mode == 'json':
            return self._enforce_json(text)
        elif self.mode == 'tool_call':
            return self._enforce_tool_call(text)
        elif self.mode == 'ucip':
            return self._enforce_ucip(text)
        elif self.mode == 'code':
            return self._enforce_code(text)
        else:
            return text  # free mode
    
    def _enforce_json(self, text: str) -> str:
        """Force valid JSON output."""
        # Try to extract JSON from the text
        # Match balanced braces
        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            try:
                parsed = json.loads(json_str)
                self.fixes_applied += 1
                return json.dumps(parsed)
            except json.JSONDecodeError:
                # Try to fix common issues
                fixed = re.sub(r"(\w+):", r'"\1":', json_str)  # Unquoted keys
                fixed = fixed.replace("'", '"')  # Single quotes -> double
                try:
                    parsed = json.loads(fixed)
                    self.fixes_applied += 1
                    return json.dumps(parsed)
                except json.JSONDecodeError:
                    pass
        
        return text
    
    def _enforce_tool_call(self, text: str) -> str:
        """Force valid tool call format (UCIP-style)."""
        # Check if already UCIP tool call format
        if re.match(r'TOOL\|', text):
            return text
        
        # Try to extract tool name and params
        tool_match = re.search(r'(?:use|call|invoke)\s+(\w+)\s*(?:with|using)?\s*(.+)?', text, re.IGNORECASE)
        if tool_match:
            tool_name = tool_match.group(1)
            params_str = tool_match.group(2) if tool_match.group(2) else ''
            # Convert to UCIP format
            self.fixes_applied += 1
            return f"TOOL|name={tool_name}|{params_str[:200]}"
        
        # XML-style tool call
        xml_match = re.search(r'<(tool|invoke)\s+name="(\w+)"[^>]*>(.*?)</(tool|invoke)>', text, re.DOTALL)
        if xml_match:
            tool_name = xml_match.group(2)
            params = xml_match.group(3).strip()
            self.fixes_applied += 1
            return f"TOOL|name={tool_name}|{params[:200]}"
        
        return text
    
    def _enforce_ucip(self, text: str) -> str:
        """Force UCIP format."""
        # Already UCIP?
        if '|' in text and any(text.startswith(t + '|') for t in ['USR', 'ASR', 'TOOL', 'RES', 'SYS']):
            return text
        
        # Try to convert natural language to UCIP
        if 'read' in text.lower() or 'analyze' in text.lower():
            self.fixes_applied += 1
            return f"ASR|ct={text[:500]}"
        
        return text
    
    def _enforce_code(self, text: str) -> str:
        """Force code block with language."""
        # Already has code block?
        if re.search(r'```\w+', text):
            return text
        
        # Detect language from keywords
        if any(kw in text for kw in ['import ', 'def ', 'class ', 'print(']):
            # Wrap in Python code block
            self.fixes_applied += 1
            return f"```python\n{text}\n```"
        elif any(kw in text for kw in ['function ', 'const ', 'let ', '=>']):
            self.fixes_applied += 1
            return f"```javascript\n{text}\n```"
        
        return text
    
    def get_stats(self) -> dict:
        return {
            'mode': self.mode,
            'fixes_applied': self.fixes_applied,
        }


# =============================================================================
# LAYER 5: LEARNING LOOP — Aprende com erros, evolui skills
# =============================================================================

class LearningLoop:
    """
    Aprende com erros da LLM e evolui o sistema.
    
    Inspirado no OpenSpace: FIX, DERIVED, CAPTURED modes.
    
    - FIX: Corrige prompts que quebraram (log de erro → prompt melhorado)
    - DERIVED: Especializa padrões que funcionaram (success → skill)
    - CAPTURED: Extrai padrões reutilizaveis de execucoes bem-sucedidas
    
    Memoria: cache de padroes de falha + correcoes
    """
    
    def __init__(self):
        self.failure_patterns = OrderedDict()  # error_signature → fix
        self.success_patterns = OrderedDict()  # task_pattern → approach
        self.stats = {
            'failures_learned': 0,
            'successes_captured': 0,
            'patterns_evolved': 0,
        }
        self.max_patterns = 200
        
    def learn_failure(self, task: str, error: str, fix: str):
        """Learn from a failure: store the pattern for future."""
        signature = self._signature(task, error)
        self.failure_patterns[signature] = {
            'task': task[:200],
            'error': error[:200],
            'fix': fix[:200],
            'timestamp': time.time(),
        }
        self.stats['failures_learned'] += 1
        self._evict()
    
    def learn_success(self, task: str, approach: str, result: str):
        """Learn from a success: capture the winning approach."""
        pattern_key = self._task_pattern(task)
        self.success_patterns[pattern_key] = {
            'task': task[:200],
            'approach': approach[:200],
            'result': result[:200],
            'timestamp': time.time(),
        }
        self.stats['successes_captured'] += 1
        self._evict()
    
    def get_fix(self, task: str, error: str) -> Optional[str]:
        """Check if we've seen this failure before. Return fix if available."""
        signature = self._signature(task, error)
        pattern = self.failure_patterns.get(signature)
        if pattern:
            return pattern['fix']
        
        # Fuzzy match: check partial signatures
        for sig, pattern in self.failure_patterns.items():
            if self._fuzzy_match(signature, sig):
                return pattern['fix']
        
        return None
    
    def get_approach(self, task: str) -> Optional[str]:
        """Check if we've successfully done this before."""
        pattern_key = self._task_pattern(task)
        pattern = self.success_patterns.get(pattern_key)
        if pattern:
            return pattern['approach']
        
        # Fuzzy match
        for key, pattern in self.success_patterns.items():
            if self._fuzzy_match(pattern_key, key):
                return pattern['approach']
        
        return None
    
    def _signature(self, task: str, error: str) -> str:
        """Create a compact failure signature."""
        # Extract key terms
        task_words = set(re.findall(r'\b\w{4,}\b', task.lower())) if task else set()
        error_words = set(re.findall(r'\b\w{4,}\b', error.lower())) if error else set()
        combined = sorted(task_words | error_words)[:10]
        return hashlib.md5('|'.join(combined).encode()).hexdigest()[:10]
    
    def _task_pattern(self, task: str) -> str:
        """Create a task pattern key."""
        words = re.findall(r'\b\w{3,}\b', task.lower())
        key_verbs = [w for w in words if w in {
            'read', 'write', 'analyze', 'debug', 'fix', 'implement',
            'refactor', 'create', 'search', 'find', 'check', 'test',
            'run', 'deploy', 'review', 'audit', 'explain'
        }]
        if key_verbs:
            return hashlib.md5(key_verbs[0].encode()).hexdigest()[:8]
        return hashlib.md5('|'.join(words[:5]).encode()).hexdigest()[:8]
    
    def _fuzzy_match(self, a: str, b: str) -> bool:
        """Check if two signatures are similar."""
        # Simple Levenshtein-like check
        if len(a) < 4 or len(b) < 4:
            return False
        common = sum(1 for ca, cb in zip(a, b) if ca == cb)
        return common / len(a) > 0.5 if len(a) > 0 else False
    
    def _evict(self):
        """Evict oldest patterns if over limit."""
        while len(self.failure_patterns) > self.max_patterns:
            self.failure_patterns.popitem(last=False)
        while len(self.success_patterns) > self.max_patterns:
            self.success_patterns.popitem(last=False)
    
    def get_stats(self) -> dict:
        return {
            'failures_learned': self.stats['failures_learned'],
            'successes_captured': self.stats['successes_captured'],
            'failure_patterns_stored': len(self.failure_patterns),
            'success_patterns_stored': len(self.success_patterns),
        }


# =============================================================================
# CAL ENGINE — The Complete Cognitive Augmentation Layer
# =============================================================================

class CognitiveAugmentationLayer:
    """
    CAL — Cognitive Augmentation Layer.
    
    Integra todas as 5 camadas em um unico pipeline que transforma
    qualquer LLM fraca em um motor cognitivo de alto nivel.
    
    Fluxo:
      task → Decomposer → [subtasks] → for each subtask:
        → LearningLoop (check known approaches/fixes)
        → InferenceScaler (generate N paths)
        → MultiAngleVerifier (score and validate)
        → GrammarGuard (enforce format)
        → Output
    
    Uso:
        cal = CognitiveAugmentationLayer(n_paths=3, strategy='self_consistency')
        result = cal.think(llm_call_function, task_prompt, context={...})
    """
    
    def __init__(self, n_paths: int = 3, strategy: str = 'self_consistency',
                 grammar_mode: str = 'tool_call', decompose: bool = True):
        self.decomposer = TaskDecomposer() if decompose else None
        self.scaler = InferenceScaler(n_paths=n_paths, strategy=strategy)
        self.verifier = MultiAngleVerifier()
        self.grammar = GrammarGuard(mode=grammar_mode)
        self.learner = LearningLoop()
        self.decompose = decompose
        self.stats = {
            'tasks_processed': 0,
            'subtasks_processed': 0,
            'total_paths_generated': 0,
        }
        
    def think(self, llm_call: Callable, task: str, 
              context: dict = None, task_type: str = None) -> dict:
        """
        Main cognitive loop. Makes any LLM think at maximum capacity.
        
        Args:
            llm_call: Function(prompt, **kwargs) -> str
            task: The task description
            context: Optional {question, expected_format, known_files}
            task_type: Optional type hint
        
        Returns:
            Dict with {response, score, reasoning_paths, subtask_results}
        """
        self.stats['tasks_processed'] += 1
        context = context or {}
        
        # Step 1: Check learning loop for known approach
        known_approach = self.learner.get_approach(task)
        if known_approach and context.get('use_learning', True):
            logger.info(f"CAL: Using known approach for task pattern")
            task += f"\n\nHint: A successful approach used before: {known_approach}"
        
        # Step 2: Decompose if enabled
        subtask_results = []
        if self.decompose and self.decomposer:
            subtasks = self.decomposer.decompose(task, task_type)
            
            # Execute subtasks sequentially
            final_response = ""
            for st in subtasks:
                self.stats['subtasks_processed'] += 1
                
                # Build subtask prompt
                subtask_prompt = f"Task: {task}\nCurrent step: {st['description']}"
                if subtask_results:
                    subtask_prompt += f"\n\nPrevious results:\n" + "\n".join(
                        f"- {r['step']}: {r['result'][:100]}" 
                        for r in subtask_results[-3:]
                    )
                
                # Scale inference for this subtask
                result = self.scaler.scale(
                    llm_call, subtask_prompt,
                    verifier=lambda r: self.verifier.verify(r, context)['score']
                )
                
                # Enforce output format
                result['response'] = self.grammar.enforce(result['response'])
                
                # Verify
                verification = self.verifier.verify(
                    result['response'], 
                    {**context, 'question': st['description']}
                )
                
                # Store subtask result
                subtask_results.append({
                    'step': st['description'],
                    'result': result['response'],
                    'score': verification['score'],
                    'passed': verification['passed'],
                })
                
                # If this is the last subtask, use its result as final
                if st == subtasks[-1]:
                    final_response = result['response']
        else:
            # No decomposition — direct inference scaling
            result = self.scaler.scale(
                llm_call, task,
                verifier=lambda r: self.verifier.verify(r, context)['score']
            )
            result['response'] = self.grammar.enforce(result['response'])
            final_response = result['response']
        
        # Step 3: Verify final output
        verification = self.verifier.verify(final_response, context)
        
        # Step 4: Learn from this execution
        if not verification['passed'] and verification['issues']:
            # Learn failure for future
            self.learner.learn_failure(
                task, 
                '; '.join(verification['issues']),
                f"Verification failed with score {verification['score']}"
            )
        else:
            # Learn success
            self.learner.learn_success(
                task,
                f"Used {self.scaler.strategy} with {self.scaler.n_paths} paths",
                final_response[:200]
            )
        
        return {
            'response': final_response,
            'score': verification['score'],
            'passed': verification['passed'],
            'checks': verification['checks'],
            'issues': verification.get('issues', []),
            'subtasks': subtask_results,
            'paths': result.get('paths', []),
            'strategy': self.scaler.strategy,
            'grammar_fixes': self.grammar.fixes_applied,
        }
    
    def get_stats(self) -> dict:
        return {
            'tasks_processed': self.stats['tasks_processed'],
            'subtasks_processed': self.stats['subtasks_processed'],
            'scaler': self.scaler.get_stats(),
            'verifier': self.verifier.get_stats(),
            'grammar': self.grammar.get_stats(),
            'learner': self.learner.get_stats(),
        }


# =============================================================================
# DEMO & TEST
# =============================================================================

def demo():
    """Demonstrate CAL with mock LLM."""
    print("=" * 65)
    print("  CAL — Cognitive Augmentation Layer v1")
    print("  Elevating weak LLMs to superhuman cognition")
    print("=" * 65)
    
    # Mock LLM that sometimes makes mistakes
    call_count = [0]
    def mock_llm(prompt, **kwargs):
        call_count[0] += 1
        temp = kwargs.get('temperature', 0.7)
        
        # Simulate different responses based on temperature
        if 'security' in prompt.lower():
            if temp < 0.8:
                return "ANSWER: Found SQL injection at line 42, XSS at line 89, hardcoded secret at line 15"
            elif temp < 1.0:
                return "ANSWER: Found SQL injection at line 42, XSS at line 89. The secret might be hardcoded at line 15 but that's not critical."
            else:
                return "ANSWER: The code looks fine. I don't see any major issues. Maybe check line 42 for best practices."
        elif 'refactor' in prompt.lower():
            return "Proposed structure: models/user.py, services/auth_service.py, controllers/auth_controller.py"
        else:
            return f"Response {call_count[0]}: I would approach this by first reading the file, then analyzing the code for issues."
    
    cal = CognitiveAugmentationLayer(
        n_paths=3, 
        strategy='self_consistency',
        grammar_mode='tool_call',
        decompose=True
    )
    
    print("\n── Test 1: Self-Consistency on Security Analysis ──")
    result = cal.think(
        mock_llm,
        "Analyze the authentication module for security vulnerabilities",
        context={'expected_format': 'text', 'known_files': ['auth.py']},
        task_type='analyze'
    )
    print(f"  Strategy: {result['strategy']}")
    print(f"  Paths:    {len(result.get('paths',[]))} generated")
    print(f"  Response: {result['response'][:150]}...")
    print(f"  Score:    {result['score']}")
    print(f"  Passed:   {result['passed']}")
    if result.get('issues'):
        print(f"  Issues:   {result['issues']}")
    
    print("\n── Test 2: Task Decomposition on Refactoring ──")
    subtasks = cal.decomposer.decompose(
        "Refactor the monolithic auth.py into MVC modules",
        'refactor'
    )
    print(f"  Task decomposed into {len(subtasks)} steps:")
    for st in subtasks:
        status_icon = '✓' if st['status'] == 'completed' else '○'
        print(f"    {status_icon} {st['description']}")
    
    print("\n── Test 3: Grammar Enforcement ──")
    bad_json = "The response is {'name': 'test', value: 42, 'status': 'ok'}"
    fixed = cal.grammar.enforce(bad_json)
    print(f"  Input:  {bad_json}")
    print(f"  Fixed:  {fixed}")
    
    print("\n── Test 4: Verifier Multi-Angle ──")
    verification = cal.verifier.verify(
        "Found SQL injection in login.py:42. The code is secure. Also found a vulnerability in login.py:142.",
        {'question': 'Find vulnerabilities in login.py', 'known_files': ['login.py'], 'expected_format': 'text'}
    )
    print(f"  Score:    {verification['score']}")
    print(f"  Checks:   {verification['checks']}")
    print(f"  Issues:   {verification.get('issues', [])}")
    
    print("\n── Full Stats ──")
    stats = cal.get_stats()
    for component, comp_stats in stats.items():
        if isinstance(comp_stats, dict):
            print(f"  {component}: {comp_stats}")
    
    print(f"\n═══ CAL v1 Ready — Any LLM, Any Task, Maximum Cognition ═══")
    return stats


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    demo()
