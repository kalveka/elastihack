(() => {
    const conversation = document.getElementById("conversation");
    const form = document.getElementById("promptForm");
    const promptInput = document.getElementById("promptInput");
    const submitButton = document.getElementById("submitPrompt");
    const messageTemplate = document.getElementById("messageTemplate");
    const openDocs = document.getElementById("openDocs");

    if (!conversation || !form || !promptInput || !submitButton || !messageTemplate) {
        console.warn("Meta-agent console assets missing expected DOM nodes.");
        return;
    }

    if (openDocs) {
        openDocs.addEventListener("click", () => {
            window.open("/docs", "_blank", "noopener");
        });
    }

    const scrollToBottom = () => {
        requestAnimationFrame(() => {
            conversation.scrollTop = conversation.scrollHeight;
        });
    };

    const createMessageElement = (role) => {
        const node = messageTemplate.content.firstElementChild.cloneNode(true);
        node.classList.add(role === "user" ? "message--user" : "message--agent");
        const avatar = node.querySelector(".message__avatar");
        avatar.textContent = role === "user" ? "You" : "A";
        return node;
    };

    const setMessageContent = (messageEl, body, meta) => {
        const bodyContainer = messageEl.querySelector(".message__body");
        const metaContainer = messageEl.querySelector(".message__meta");

        bodyContainer.innerHTML = "";
        metaContainer.innerHTML = "";

        if (typeof body === "string") {
            bodyContainer.textContent = body;
        } else if (body instanceof Node) {
            bodyContainer.appendChild(body);
        } else if (Array.isArray(body)) {
            body.forEach((entry) => {
                if (typeof entry === "string") {
                    const p = document.createElement("p");
                    p.textContent = entry;
                    bodyContainer.appendChild(p);
                } else if (entry instanceof Node) {
                    bodyContainer.appendChild(entry);
                }
            });
        }

        if (meta) {
            if (typeof meta === "string") {
                metaContainer.textContent = meta;
            } else if (meta instanceof Node) {
                metaContainer.appendChild(meta);
            }
        }
    };

    const addMessage = (role, body, meta) => {
        const el = createMessageElement(role);
        setMessageContent(el, body, meta);
        conversation.appendChild(el);
        scrollToBottom();
        return el;
    };

    const updateMessage = (messageEl, body, meta) => {
        setMessageContent(messageEl, body, meta);
        scrollToBottom();
    };

    const formatArray = (items) => {
        if (!Array.isArray(items) || items.length === 0) {
            return null;
        }
        const list = document.createElement("ul");
        items.forEach((item) => {
            const li = document.createElement("li");
            li.textContent = typeof item === "string" ? item : JSON.stringify(item, null, 2);
            list.appendChild(li);
        });
        return list;
    };

    const createSection = (title, bodyNodes) => {
        const section = document.createElement("div");
        section.className = "result-section";

        const heading = document.createElement("h3");
        heading.textContent = title;
        section.appendChild(heading);

        bodyNodes.forEach((node) => {
            if (!node) {
                return;
            }
            if (typeof node === "string") {
                const para = document.createElement("p");
                para.textContent = node;
                section.appendChild(para);
            } else {
                section.appendChild(node);
            }
        });

        return section;
    };

    const verdictBadge = (verdict) => {
        if (!verdict) {
            return null;
        }

        const span = document.createElement("span");
        span.className = "badge";
        span.dataset.verdict = verdict;

        const normalized = verdict.toLowerCase();
        const label = normalized.charAt(0).toUpperCase() + normalized.slice(1);

        if (normalized === "approve") {
            span.classList.add("badge--approve");
        } else if (normalized === "caution") {
            span.classList.add("badge--caution");
        } else {
            span.classList.add("badge--reject");
        }

        span.textContent = label;
        return span;
    };

    const normalizeExcerpt = (value) => {
        if (!value) {
            return undefined;
        }
        if (Array.isArray(value)) {
            return value[0];
        }
        return typeof value === "string" ? value : JSON.stringify(value);
    };

    const formatContext = (context) => {
        const container = document.createDocumentFragment();
        if (!context) {
            container.appendChild(document.createTextNode("No supporting context returned."));
            return container;
        }

        const { elastic = [], research = [] } = context;

        if (elastic.length > 0) {
            const list = document.createElement("ul");
            elastic.forEach((doc) => {
                const li = document.createElement("li");
                const title = doc.title || doc.id || "Elastic document";
                const excerpt = normalizeExcerpt(doc.excerpt);
                li.innerHTML = `<strong>${title}</strong>${excerpt ? ` — ${excerpt}` : ""}`;
                list.appendChild(li);
            });
            container.appendChild(createSection("Elastic context", [list]));
        }

        if (research.length > 0) {
            const list = document.createElement("ul");
            research.forEach((doc) => {
                const li = document.createElement("li");
                const title = doc.title || "Research article";
                if (doc.url) {
                    const link = document.createElement("a");
                    link.href = doc.url;
                    link.textContent = title;
                    link.target = "_blank";
                    link.rel = "noreferrer noopener";
                    li.appendChild(link);
                } else {
                    li.textContent = title;
                }
                if (doc.summary) {
                    const summary = document.createElement("p");
                    summary.textContent = doc.summary;
                    li.appendChild(summary);
                }
                list.appendChild(li);
            });
            container.appendChild(createSection("Research context", [list]));
        }

        if (elastic.length === 0 && research.length === 0) {
            container.appendChild(document.createTextNode("No supporting context returned."));
        }

        return container;
    };

    const formatRecommendation = (rec) => {
        if (!rec) {
            return createSection("Recommendation", ["No recommendation returned."]);
        }

        const recommended = rec.recommended_model && typeof rec.recommended_model === "object"
            ? rec.recommended_model
            : rec;

        const nodes = [];
        const headline = document.createElement("p");
        const modelName = recommended.model_name || rec.model_name || "Unknown model";
        const modelId = recommended.model_id || rec.model_id;
        headline.innerHTML = `<strong>${modelName}</strong>${modelId ? ` · <code>${modelId}</code>` : ""}`;
        nodes.push(headline);

        if (recommended.reasoning) {
            const rationale = document.createElement("p");
            rationale.textContent = recommended.reasoning;
            nodes.push(rationale);
        }

        if (recommended.alignment) {
            const alignment = document.createElement("p");
            alignment.textContent = `Alignment: ${recommended.alignment}`;
            nodes.push(alignment);
        }

        if (Array.isArray(rec.governance_notes) && rec.governance_notes.length > 0) {
            const heading = document.createElement("p");
            heading.innerHTML = "<strong>Governance notes</strong>";
            nodes.push(heading);
            const governanceList = formatArray(rec.governance_notes);
            if (governanceList) {
                nodes.push(governanceList);
            }
        }

        if (Array.isArray(rec.candidate_models) && rec.candidate_models.length > 0) {
            const heading = document.createElement("p");
            heading.innerHTML = "<strong>Candidate models</strong>";
            nodes.push(heading);
            const list = document.createElement("ul");
            rec.candidate_models.slice(0, 3).forEach((candidate) => {
                if (!candidate || typeof candidate !== "object") {
                    return;
                }
                const item = document.createElement("li");
                const name = candidate.model_name || candidate.name || candidate.model_id || "Candidate";
                const id = candidate.model_id || candidate.id;
                const titleParts = [`${name}`];
                if (id) {
                    titleParts.push(`<code>${id}</code>`);
                }
                item.innerHTML = titleParts.join(" · ");
                if (candidate.reasoning) {
                    const rationale = document.createElement("p");
                    rationale.textContent = candidate.reasoning;
                    item.appendChild(rationale);
                }
                if (Array.isArray(candidate.policy_notes) && candidate.policy_notes.length > 0) {
                    const policyLabel = document.createElement("p");
                    policyLabel.innerHTML = "<em>Policy notes</em>";
                    item.appendChild(policyLabel);
                    const notesList = formatArray(candidate.policy_notes);
                    if (notesList) {
                        item.appendChild(notesList);
                    }
                }
                list.appendChild(item);
            });
            nodes.push(list);
        }

        if (rec.bedrock_status && typeof rec.bedrock_status === "object") {
            const { catalog_count: catalogCount, error } = rec.bedrock_status;
            const status = document.createElement("p");
            const countText = typeof catalogCount === "number"
                ? `${catalogCount} model${catalogCount === 1 ? "" : "s"} detected`
                : "Model catalog unavailable";
            status.innerHTML = `<em>Bedrock status:</em> ${countText}${error ? ` — ${error}` : ""}`;
            nodes.push(status);
        }

        return createSection("Recommendation", nodes);
    };

    const formatJudge = (judge) => {
        if (!judge) {
            return createSection("Judge verdict", ["No evaluation available."]);
        }

        const nodes = [];
        const verdictRow = document.createElement("div");
        verdictRow.style.display = "flex";
        verdictRow.style.alignItems = "center";
        verdictRow.style.gap = "8px";

        const badge = verdictBadge(judge.verdict || "caution");
        if (badge) {
            verdictRow.appendChild(badge);
        }

        if (judge.verdict) {
            const label = document.createElement("span");
            label.textContent = `Verdict: ${judge.verdict}`;
            verdictRow.appendChild(label);
        }

        nodes.push(verdictRow);

        const risks = formatArray(judge.risks);
        if (risks) {
            nodes.push(createSection("Key risks", [risks]));
        }

        const suggestions = formatArray(judge.suggestions);
        if (suggestions) {
            nodes.push(createSection("Next steps", [suggestions]));
        }

        const section = createSection("Judge verdict", []);
        nodes.forEach((node) => section.appendChild(node));
        return section;
    };

    const renderResult = (data) => {
        const fragment = document.createDocumentFragment();
        fragment.appendChild(formatRecommendation(data.recommendation));
        fragment.appendChild(formatJudge(data.judge));
        fragment.appendChild(createSection("Context", [formatContext(data.context)]));
        return fragment;
    };

    const parseRegulatory = (value) => {
        if (!value) {
            return [];
        }
        return value
            .split(",")
            .map((entry) => entry.trim())
            .filter(Boolean);
    };

    const buildPayload = (formData) => {
        const prompt = formData.get("prompt")?.toString().trim() ?? "";
        const maxContext = Number.parseInt(formData.get("max_context")?.toString() ?? "3", 10);

        const requirements = {
            industry: formData.get("industry")?.toString().trim() || null,
            data_sensitivity: formData.get("data_sensitivity")?.toString() || "internal",
            budget_tier: formData.get("budget_tier")?.toString() || "medium",
            latency_tolerance_ms: formData.get("latency_tolerance_ms")
                ? Number.parseInt(formData.get("latency_tolerance_ms").toString(), 10)
                : null,
            regulatory_frameworks: parseRegulatory(formData.get("regulatory_frameworks")?.toString() ?? ""),
        };

        if (!requirements.industry) {
            delete requirements.industry;
        }
        if (!requirements.latency_tolerance_ms || Number.isNaN(requirements.latency_tolerance_ms)) {
            delete requirements.latency_tolerance_ms;
        }
        if (requirements.regulatory_frameworks.length === 0) {
            delete requirements.regulatory_frameworks;
        }

        return {
            prompt,
            max_context: Number.isNaN(maxContext) ? 3 : Math.min(Math.max(maxContext, 1), 10),
            requirements,
        };
    };

    const handleSubmit = async (event) => {
        event.preventDefault();

        const formData = new FormData(form);
        const payload = buildPayload(formData);

        if (!payload.prompt) {
            promptInput.focus();
            return;
        }

        const userMessage = addMessage("user", payload.prompt);

        submitButton.disabled = true;
        submitButton.textContent = "Running...";

        const placeholder = addMessage("agent", [
            "Processing your request...",
            "Fetching context from Elastic and research providers.",
        ]);

        try {
            const response = await fetch("/meta-agent", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                const detail = await response.json().catch(() => ({}));
                const message = detail?.detail || response.statusText || "Unexpected error";
                throw new Error(message);
            }

            const data = await response.json();
            updateMessage(placeholder, renderResult(data));
            const meta = document.createElement("span");
            meta.textContent = new Date().toLocaleTimeString();
            placeholder.querySelector(".message__meta").appendChild(meta);
        } catch (error) {
            const reason = error instanceof Error ? error.message : "Unknown error";
            updateMessage(placeholder, `Unable to complete the request: ${reason}`, "Please try again after checking credentials.");
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = "Send";
            promptInput.value = "";
            promptInput.focus();
        }
    };

    form.addEventListener("submit", handleSubmit);
})();
