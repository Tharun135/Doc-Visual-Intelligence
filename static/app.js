/**
 * DOCUMENTATION VISUALIZATION ASSISTANT - CLIENT SIDE INTERACTIVITY
 */

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initFileUpload();
    initResultsPanel();
    initGifTimelines();
    initFormLoading();
    initArtifactTools();
    initInsertButtons();
    initHelpModal();
    initVisualPreview();
    initPrivacyVerification();
});

const PRIVACY_MODE_ENABLED = document.body?.dataset?.privacyMode === '1';

function initPrivacyVerification() {
    const triggerBtn = document.getElementById('privacyVerifyBtn');
    const card = document.getElementById('privacyVerificationCard');
    const checksList = document.getElementById('privacyChecksList');
    const scoreBadge = document.getElementById('privacyScoreBadge');
    if (!triggerBtn || !card || !checksList || !scoreBadge) {
        return;
    }

    const renderCheck = (check) => {
        const pass = !!check.pass;
        const icon = pass ? '✔' : '✖';
        const color = pass ? 'var(--accent-emerald)' : 'var(--accent-rose)';
        return `<div style="display:flex; align-items:center; gap:0.5rem;"><span style="color:${color}; font-weight:700;">${icon}</span><span>${check.name}</span></div>`;
    };

    const runVerification = async () => {
        triggerBtn.setAttribute('disabled', 'disabled');
        scoreBadge.textContent = 'Running';
        card.style.display = 'block';
        checksList.innerHTML = '<div style="color:var(--text-muted);">Running privacy checks...</div>';
        try {
            const response = await fetch('/privacy/report', { method: 'GET' });
            const data = await response.json();
            if (!response.ok || !data.ok) {
                throw new Error(data.error || 'Privacy verification failed');
            }

            scoreBadge.textContent = `${data.score}/100`;
            scoreBadge.style.color = data.score === 100 ? 'var(--accent-emerald)' : 'var(--accent-amber)';
            checksList.innerHTML = (data.checks || []).map(renderCheck).join('');
        } catch (error) {
            scoreBadge.textContent = 'Error';
            scoreBadge.style.color = 'var(--accent-rose)';
            checksList.innerHTML = '<div style="color:var(--accent-rose);">Unable to run verification report.</div>';
        } finally {
            triggerBtn.removeAttribute('disabled');
        }
    };

    triggerBtn.addEventListener('click', runVerification);
    if (PRIVACY_MODE_ENABLED) {
        runVerification();
    }
}



/**
 * Tab Switching Logic
 */
function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');
    const fileInput = document.querySelector('.file-input');
    const pastedText = document.querySelector('[name="pasted_text"]');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.tab;

            // Toggle active buttons
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Toggle active panels
            tabPanels.forEach(p => p.classList.remove('active'));
            const activePanel = document.getElementById(`${target}-panel`);
            if (activePanel) activePanel.classList.add('active');

            // Clear validation fields to avoid conflicting submissions
            if (target === 'upload') {
                pastedText.removeAttribute('required');
                if (!fileInput.files.length) {
                    fileInput.setAttribute('required', 'required');
                }
            } else {
                fileInput.removeAttribute('required');
                pastedText.setAttribute('required', 'required');
            }
        });
    });
}

/**
 * File Upload Interactivity
 */
function initFileUpload() {
    const uploadZone = document.querySelector('.upload-zone');
    const fileInput = document.querySelector('.file-input');
    const banner = document.querySelector('.selected-file-banner');
    const bannerName = document.querySelector('.selected-file-name');
    const removeBtn = document.querySelector('.remove-file-btn');
    const textTabBtn = document.querySelector('[data-tab="text"]');
    const uploadTabBtn = document.querySelector('[data-tab="upload"]');

    if (!uploadZone) return;

    // Trigger click on input
    uploadZone.addEventListener('click', () => {
        fileInput.click();
    });

    // Drag-over styling
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
        }, false);
    });

    // Drop file
    uploadZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;

        if (files.length) {
            fileInput.files = files;
            updateFileBanner(files[0].name);
        }
    });

    // Change file
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) {
            updateFileBanner(fileInput.files[0].name);
        }
    });

    // Remove file
    removeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        fileInput.value = '';
        banner.style.display = 'none';
        uploadZone.style.display = 'block';
        fileInput.setAttribute('required', 'required');
    });

    function updateFileBanner(name) {
        bannerName.textContent = name;
        banner.style.display = 'flex';
        uploadZone.style.display = 'none';
        fileInput.removeAttribute('required');
    }
}



/**
 * Form Submission Loading State
 */
function initFormLoading() {
    const form = document.querySelector('form');
    const submitBtn = document.querySelector('.btn-submit');
    const spinner = document.querySelector('.spinner');
    const btnText = document.querySelector('.btn-text');

    if (!form) return;

    form.addEventListener('submit', () => {
        submitBtn.setAttribute('disabled', 'disabled');
        spinner.style.display = 'inline-block';
        btnText.textContent = 'Scanning Document...';
    });
}

/**
 * Results Pane Navigation and Highlight Sync
 */
function initResultsPanel() {
    const sectionItems = document.querySelectorAll('.section-item-card');
    const detailPanels = document.querySelectorAll('.detail-panel');
    const detailContainer = document.querySelector('.detail-container');

    if (!sectionItems.length) return;

    sectionItems.forEach(item => {
        item.addEventListener('click', () => {
            const index = item.dataset.index;

            // Remove active status
            sectionItems.forEach(si => si.classList.remove('active'));
            item.classList.add('active');

            // Hide all detail panels and show target
            detailPanels.forEach(dp => dp.classList.remove('active'));
            const targetPanel = document.getElementById(`detail-${index}`);
            if (targetPanel) {
                targetPanel.classList.add('active');
                highlightContentKeywords(targetPanel);
                
                // Scroll detail container to top with small delay to ensure render
                if (detailContainer) {
                    setTimeout(() => {
                        detailContainer.scroll({ top: 0, behavior: 'smooth' });
                    }, 10);
                }
            }
        });
    });

    // Auto-select the first section
    sectionItems[0].click();
}

/**
 * Highlight important trigger words inside the display source block
 */
function highlightContentKeywords(detailPanel) {
    const contentBox = detailPanel.querySelector('.section-content-box');
    if (!contentBox || contentBox.dataset.highlighted === 'true') return;

    let text = contentBox.innerHTML;

    // Define rules keywords to match
    const uiKeywords = ['click', 'button', 'menu', 'tab', 'window', 'dialog'];
    const archKeywords = ['plc', 'hmi', 'server', 'gateway', 'network'];
    const logicKeywords = ['if', 'else', 'otherwise', 'then'];
    const setupKeywords = ['cable', 'mount', 'power supply', 'device', 'mounting'];
    const transferKeywords = ['import', 'export', 'upload', 'download', 'synchronisation', 'sync'];
    const formatKeywords = ['json', 'xml', 'yaml'];
    const topologyKeywords = ['device', 'connector', 'edge device', 'plc', 'cloud', 'gateway', 'network'];
    const dataFlowKeywords = ['collect', 'send', 'transfer', 'publish', 'subscribe', 'data flow'];

    // Escape regex characters helper
    const escapeRegExp = string => string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

    // Apply Highlight
    const applyRegexHighlight = (keywords, cssClass) => {
        keywords.forEach(kw => {
            const regex = new RegExp(`\\b(${escapeRegExp(kw)})\\b`, 'gi');
            text = text.replace(regex, `<span class="${cssClass}">$1</span>`);
        });
    };

    applyRegexHighlight(uiKeywords, 'highlight-term');
    applyRegexHighlight(archKeywords, 'highlight-term');
    applyRegexHighlight(logicKeywords, 'highlight-term');
    applyRegexHighlight(setupKeywords, 'highlight-term');
    applyRegexHighlight(transferKeywords, 'highlight-term');
    applyRegexHighlight(formatKeywords, 'highlight-term');
    applyRegexHighlight(topologyKeywords, 'highlight-term');
    applyRegexHighlight(dataFlowKeywords, 'highlight-term');

    // Highlight steps (numbers starting a line)
    const stepRegex = /(^\d+[\.\)]|^\bstep\s+\d+\b)/gim;
    text = text.replace(stepRegex, '<span class="highlight-step">$1</span>');

    contentBox.innerHTML = text;
    contentBox.dataset.highlighted = 'true';
}

/**
 * GIF Timeline frames micro-animations controller
 */
function initGifTimelines() {
    const timelines = document.querySelectorAll('.gif-sim-timeline');
    
    timelines.forEach(timeline => {
        const frames = timeline.querySelectorAll('.frame-card');
        const progressBar = timeline.querySelector('.gif-timeline-progress');
        const statusText = timeline.querySelector('.status-step');
        
        let activeIndex = 0;
        const totalFrames = frames.length;
        
        if (totalFrames === 0) return;

        // Loop animation
        setInterval(() => {
            // Remove active class
            frames.forEach(f => f.classList.remove('active'));
            
            // Set next frame active
            activeIndex = (activeIndex + 1) % totalFrames;
            const currentFrame = frames[activeIndex];
            currentFrame.classList.add('active');
            
            // Update progress bar
            const pct = ((activeIndex + 1) / totalFrames) * 100;
            progressBar.style.width = `${pct}%`;
            
            // Update Status text
            if (statusText) {
                statusText.textContent = `Frame ${activeIndex + 1}/${totalFrames}`;
            }

            // Simulate cursor position on active frame
            const cursor = currentFrame.querySelector('.cursor-sim');
            const visual = currentFrame.querySelector('.frame-visual');
            if (cursor && visual) {
                // Generate random point in frame to animate mouse pointer
                const x = Math.floor(Math.random() * (visual.clientWidth - 15));
                const y = Math.floor(Math.random() * (visual.clientHeight - 15));
                cursor.style.left = `${x}px`;
                cursor.style.top = `${y}px`;
            }
        }, 1500);
    });
}


// Collapsible Details Toggle for Recommendation Cards
function initDetailsToggle() {
    // Handle old details toggle
    document.querySelectorAll('.reco-details-toggle').forEach(button => {
        if (button.dataset.bound === 'true') {
            return;
        }
        button.dataset.bound = 'true';
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const isExpanded = this.getAttribute('aria-expanded') === 'true';
            this.setAttribute('aria-expanded', !isExpanded);
            
            const content = this.nextElementSibling;
            if (content && content.classList.contains('reco-details-content')) {
                if (isExpanded) {
                    content.style.maxHeight = '0';
                } else {
                    content.style.maxHeight = content.scrollHeight + 'px';
                }
            }
        });
    });
    
    // Handle new advanced toggle (writer-focused)
    document.querySelectorAll('.reco-advanced-toggle').forEach(button => {
        if (button.dataset.bound === 'true') {
            return;
        }
        button.dataset.bound = 'true';
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const isExpanded = this.getAttribute('aria-expanded') === 'true';
            this.setAttribute('aria-expanded', !isExpanded);
            
            const content = this.nextElementSibling;
            if (content && content.classList.contains('reco-advanced-content')) {
                if (isExpanded) {
                    content.style.maxHeight = '0';
                } else {
                    content.style.maxHeight = content.scrollHeight + 'px';
                }
            }
        });
    });
}


function initArtifactTools() {
    document.querySelectorAll('.copy-artifact-btn').forEach(button => {
        if (button.dataset.bound === 'true') {
            return;
        }
        button.dataset.bound = 'true';
        button.addEventListener('click', async () => {
            const targetId = button.dataset.copyTarget;
            const target = document.getElementById(targetId);
            if (!target) {
                return;
            }

            try {
                await navigator.clipboard.writeText(target.textContent.trim());
                const original = button.textContent;
                button.textContent = 'Copied';
                window.setTimeout(() => {
                    button.textContent = original;
                }, 1200);
            } catch (error) {
                button.textContent = 'Unavailable';
            }
        });
    });

    if (window.mermaid) {
        window.mermaid.initialize({
            startOnLoad: false,
            securityLevel: 'strict',
            htmlLabels: false,
            flowchart: {
                htmlLabels: false,
                useMaxWidth: true,
            },
            theme: 'dark'
        });
        document.querySelectorAll('.artifact-mermaid-preview').forEach((preview, index) => {
            if (preview.closest('.artifact-hidden')) {
                return;
            }
            if (preview.dataset.rendered === 'true') {
                return;
            }
            preview.dataset.rendered = 'true';
            const source = preview.textContent;
            window.mermaid.render(`artifact-preview-${index}`, source).then(({ svg }) => {
                preview.innerHTML = svg;
                applyWorkflowAnimation(preview);
            }).catch(() => {
                preview.textContent = source;
            });
        });
    }
}

function renderMermaidInContainer(container) {
    if (!window.mermaid || !container) {
        return;
    }

    container.querySelectorAll('.artifact-mermaid-preview').forEach((preview, index) => {
        if (preview.dataset.rendered === 'true') {
            return;
        }
        preview.dataset.rendered = 'true';
        const source = preview.textContent;
        window.mermaid.render(`artifact-preview-generated-${Date.now()}-${index}`, source).then(({ svg }) => {
            preview.innerHTML = svg;
            applyWorkflowAnimation(preview);
        }).catch(() => {
            preview.textContent = source;
        });
    });
}

function applyWorkflowAnimation(preview) {
    if (!preview || preview.dataset.animated === 'true') {
        return;
    }

    const visualType = (preview.dataset.visualType || '').trim().toLowerCase();
    if (visualType !== 'workflow diagram') {
        return;
    }

    const svg = preview.querySelector('svg');
    if (!svg) {
        return;
    }

    preview.classList.add('workflow-animated');

    // Primary edge selectors from Mermaid flowcharts.
    let edgePaths = Array.from(svg.querySelectorAll('.edgePath .path, .flowchart-link, .edge-thickness-normal, .edge-thickness-thick'));

    // Fallback: if Mermaid theme/classes differ, animate path elements that are likely links.
    if (edgePaths.length === 0) {
        edgePaths = Array.from(svg.querySelectorAll('path')).filter((path) => {
            return !path.closest('defs') && !path.closest('.node') && !path.closest('.label');
        });
    }

    edgePaths.forEach((edge, index) => {
        edge.style.setProperty('stroke-dasharray', '8 7');
        edge.style.setProperty('animation', 'workflow-flow 1.5s linear infinite');
        edge.style.setProperty('animation-delay', `${(index % 12) * 0.16}s`);
    });

    const nodes = svg.querySelectorAll('.node rect, .node polygon, .node circle, .node ellipse');
    nodes.forEach((node, index) => {
        node.style.setProperty('animation', 'workflow-node-pulse 2s ease-in-out infinite');
        node.style.setProperty('animation-delay', `${(index % 12) * 0.18}s`);
    });

    preview.dataset.animated = 'true';
}

function initGenerateArtifactButtons() {
    document.querySelectorAll('.generate-artifact-btn').forEach(button => {
        if (button.dataset.bound === 'true') {
            return;
        }
        button.dataset.bound = 'true';

        button.addEventListener('click', () => {
            const targetId = button.dataset.targetId;
            const artifactContainer = targetId ? document.getElementById(targetId) : null;
            if (!artifactContainer) {
                return;
            }

            artifactContainer.classList.remove('artifact-hidden');
            if (artifactContainer.querySelector('.artifact-mermaid-preview')) {
                renderMermaidInContainer(artifactContainer);
            }

            button.classList.add('inserted');
            button.textContent = '✓ Generated';
        });
    });
}

function initFeedbackButtons() {
    if (PRIVACY_MODE_ENABLED) {
        document.querySelectorAll('.feedback-btn').forEach(button => {
            button.setAttribute('disabled', 'disabled');
            button.title = 'Feedback logging is disabled in Privacy Mode';
        });
        return;
    }

    document.querySelectorAll('.feedback-btn').forEach(button => {
        if (button.dataset.bound === 'true') {
            return;
        }
        button.dataset.bound = 'true';

        button.addEventListener('click', async () => {
            const card = button.closest('.reco-card');
            if (!card) {
                return;
            }

            const payload = {
                section_title: card.dataset.sectionTitle || '',
                visual_type: card.dataset.visualType || '',
                confidence: card.dataset.confidence || '',
                useful: button.dataset.useful || '',
            };

            try {
                const response = await fetch('/feedback', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });

                if (!response.ok) {
                    throw new Error('Feedback request failed');
                }

                const buttons = card.querySelectorAll('.feedback-btn');
                buttons.forEach(btn => btn.classList.remove('feedback-selected'));
                button.classList.add('feedback-selected');
                const original = button.textContent;
                button.textContent = '✓ Saved';
                setTimeout(() => {
                    button.textContent = original;
                }, 1200);
            } catch (error) {
                button.textContent = 'Retry';
            }
        });
    });
}

/**
 * PlantUML render button — calls /generate/plantuml and injects the SVG.
 */
function initPlantUMLRenderButtons() {
    document.querySelectorAll('.plantuml-render-btn').forEach(button => {
        if (button.dataset.bound === 'true') return;
        button.dataset.bound = 'true';

        button.addEventListener('click', async () => {
            const artifactId = button.dataset.artifactId;
            const code = button.dataset.plantuml;
            if (!artifactId || !code) return;

            const container = document.getElementById(`${artifactId}-plantuml-container`);
            const preview   = document.getElementById(`${artifactId}-plantuml-preview`);
            const status    = document.getElementById(`${artifactId}-plantuml-status`);

            if (!container || !preview) return;

            // Show the output panel and update state
            container.classList.remove('artifact-hidden');
            button.setAttribute('disabled', 'disabled');
            button.textContent = 'Rendering…';
            if (status) { status.textContent = 'Rendering'; status.style.color = 'var(--text-muted)'; }
            preview.innerHTML = '<span style="color:var(--text-muted);font-size:0.85rem;">Contacting PlantUML server…</span>';

            try {
                const response = await fetch('/generate/plantuml', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code }),
                });

                const data = await response.json();

                if (!response.ok || !data.ok) {
                    throw new Error(data.error || `Server error ${response.status}`);
                }

                // Inject SVG — make it responsive
                let svg = data.svg;
                svg = svg.replace(/<svg /, '<svg style="max-width:100%;height:auto;" ');
                preview.innerHTML = svg;

                if (status) { status.textContent = 'OK'; status.style.color = 'var(--confidence-high, #4ade80)'; }
                button.textContent = '✓ Rendered';
                button.classList.add('inserted');

            } catch (err) {
                preview.innerHTML = `<span style="color:var(--error-color,#f87171);font-size:0.85rem;">Render failed: ${err.message}</span>`;
                if (status) { status.textContent = 'Error'; status.style.color = 'var(--error-color,#f87171)'; }
                button.removeAttribute('disabled');
                button.textContent = 'Retry';
            }
        });
    });
}

// Placement highlight: "Show in text" button handler
function initPlacementHighlight() {
    document.querySelectorAll('.show-in-text-btn').forEach(button => {
        if (button.dataset.bound === 'true') return;
        button.dataset.bound = 'true';

        button.addEventListener('click', () => {
            const card = button.closest('.reco-card');
            const detailPanel = button.closest('.detail-panel');
            if (!card || !detailPanel) return;

            const contentBox = detailPanel.querySelector('.section-content-box');
            if (!contentBox) return;

            // Save original text once
            if (!contentBox.dataset.rawText) {
                contentBox.dataset.rawText = contentBox.textContent;
            }

            const stepLines = JSON.parse(detailPanel.dataset.stepLines || '[]');
            const placementType = card.dataset.placementType;
            const stepNumber = parseInt(card.dataset.placementStep || '0', 10);

            // Clear any existing highlights first
            clearContentHighlight(detailPanel);

            buildContentHighlight(contentBox, stepLines, placementType, stepNumber);

            // Scroll the content box into view
            contentBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

            // Toggle button state
            button.classList.add('show-in-text-active');
            button.textContent = '✓ Shown';
            setTimeout(() => {
                button.classList.remove('show-in-text-active');
                button.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px;"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg> Show in text';
            }, 3000);
        });
    });
}

function clearContentHighlight(detailPanel) {
    const contentBox = detailPanel.querySelector('.section-content-box');
    if (!contentBox || !contentBox.dataset.rawText) return;
    contentBox.textContent = contentBox.dataset.rawText;
}

function buildContentHighlight(contentBox, stepLines, placementType, stepNumber) {
    const rawText = contentBox.dataset.rawText || contentBox.textContent;
    const rawLines = rawText.split('\n');

    contentBox.innerHTML = '';

    if (placementType === 'before_section') {
        // Insert a marker before all content
        const marker = document.createElement('span');
        marker.className = 'content-insert-marker content-insert-before';
        marker.textContent = '▼ Insert diagram here (before procedure starts)';
        contentBox.appendChild(marker);
        contentBox.appendChild(document.createTextNode('\n'));
        rawLines.forEach((line, i) => {
            contentBox.appendChild(document.createTextNode(line));
            if (i < rawLines.length - 1) contentBox.appendChild(document.createTextNode('\n'));
        });
        marker.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        return;
    }

    if (placementType === 'after_step' && stepNumber > 0 && stepLines.length >= stepNumber) {
        const targetText = stepLines[stepNumber - 1].substring(0, 40).toLowerCase();
        let matchIndex = rawLines.findIndex(line => line.toLowerCase().includes(targetText));

        rawLines.forEach((line, i) => {
            if (i === matchIndex) {
                const stepEl = document.createElement('span');
                stepEl.className = 'content-step-highlight';
                stepEl.textContent = line;
                contentBox.appendChild(stepEl);

                const markerEl = document.createElement('span');
                markerEl.className = 'content-insert-marker content-insert-after-step';
                markerEl.textContent = '\n▼ Insert screenshot here';
                contentBox.appendChild(markerEl);
            } else {
                contentBox.appendChild(document.createTextNode(line));
            }
            if (i < rawLines.length - 1) contentBox.appendChild(document.createTextNode('\n'));
        });

        const highlight = contentBox.querySelector('.content-step-highlight');
        if (highlight) highlight.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        return;
    }

    // Fallback: restore plain text
    contentBox.textContent = rawText;
}

// Insert Button Handler - Visual placement tracking
function initInsertButtons() {
    document.querySelectorAll('.insert-at-placement').forEach(button => {
        if (button.dataset.bound === 'true') {
            return;
        }
        button.dataset.bound = 'true';
        button.addEventListener('click', () => {
            const placement = button.dataset.placement;
            const card = button.closest('.reco-card');
            const detailPanel = button.closest('.detail-panel');
            const visualType = card.querySelector('.reco-type-text')?.textContent || 'Visual';
            
            if (!detailPanel) return;
            
            // Highlight placement zone
            const placementIndicator = detailPanel.querySelector(
                placement === 'before' ? '.placement-start' : 
                placement === 'after' ? '.placement-end' : 
                '.placement-start'
            );
            
            if (placementIndicator) {
                // Add highlight effect
                placementIndicator.style.animation = 'none';
                setTimeout(() => {
                    placementIndicator.style.animation = 'pulse-highlight 0.6s ease-out';
                }, 10);
                
                // Scroll into view
                placementIndicator.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            
            // Update button state
            button.classList.add('inserted');
            const original = button.textContent;
            button.textContent = '✓ Inserted';
            
            setTimeout(() => {
                button.textContent = original;
                button.classList.remove('inserted');
            }, 2000);
        });
    });
}

// Call toggle init after results are loaded
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(initDetailsToggle, 100);
    setTimeout(initArtifactTools, 100);
    setTimeout(initGenerateArtifactButtons, 100);
    setTimeout(initInsertButtons, 100);
    setTimeout(initPlacementHighlight, 100);
    setTimeout(initFeedbackButtons, 100);
    setTimeout(initPlantUMLRenderButtons, 100);
});

// Also reinit when results are refreshed
const observer = new MutationObserver(() => {
    initDetailsToggle();
    initArtifactTools();
    initGenerateArtifactButtons();
    initInsertButtons();
    initPlacementHighlight();
    initFeedbackButtons();
    initPlantUMLRenderButtons();
    initVisualPreview();
});

/**
 * Initialize Help Modal
 */
function initHelpModal() {
    const helpToggleBtn = document.getElementById('helpToggleBtn');
    const closeHelpBtn = document.getElementById('closeHelpBtn');
    const helpModal = document.getElementById('helpModal');

    if (!helpToggleBtn || !closeHelpBtn || !helpModal) return;

    // Open help modal
    helpToggleBtn.addEventListener('click', () => {
        helpModal.classList.add('active');
        document.body.style.overflow = 'hidden';
    });

    // Close help modal
    closeHelpBtn.addEventListener('click', () => {
        helpModal.classList.remove('active');
        document.body.style.overflow = 'auto';
    });

    // Close on overlay click
    const overlay = helpModal.querySelector('.help-modal-overlay');
    if (overlay) {
        overlay.addEventListener('click', () => {
            helpModal.classList.remove('active');
            document.body.style.overflow = 'auto';
        });
    }

    // Close on ESC key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && helpModal.classList.contains('active')) {
            helpModal.classList.remove('active');
            document.body.style.overflow = 'auto';
        }
    });
}

/**
 * Initialize Visual Preview Modal
 */
function initVisualPreview() {
    const previewModal = document.getElementById('previewModal');
    const closePreviewBtn = document.getElementById('closePreviewBtn');
    const previewModalOverlay = document.getElementById('previewModalOverlay');
    const previewModalBody = document.getElementById('previewModalBody');
    const previewModalTitle = document.getElementById('previewModalTitle');

    if (!previewModal || !closePreviewBtn || !previewModalBody) return;

    // Attach click listener to all artifact previews
    document.querySelectorAll('.artifact-mermaid-preview, .artifact-svg-preview').forEach(preview => {
        if (preview.dataset.previewBound === 'true') return;
        preview.dataset.previewBound = 'true';
        
        // Make it look clickable
        preview.style.cursor = 'zoom-in';
        preview.title = 'Click to enlarge';
        
        preview.addEventListener('click', (e) => {
            // Check if it's already generated and has an SVG
            const svgEl = preview.querySelector('svg');
            if (!svgEl) return;
            
            // Get title from card if available
            const card = preview.closest('.reco-card');
            if (card) {
                const titleEl = card.querySelector('.reco-type-text');
                if (titleEl) {
                    previewModalTitle.textContent = titleEl.textContent + ' Preview';
                } else {
                    previewModalTitle.textContent = 'Visual Preview';
                }
            }
            
            // Clone the visual content
            previewModalBody.innerHTML = '';
            const clonedSvg = svgEl.cloneNode(true);
            
            // Allow it to scale naturally in the modal
            clonedSvg.style.width = '100%';
            clonedSvg.style.height = 'auto';
            clonedSvg.style.maxHeight = '80vh';
            
            previewModalBody.appendChild(clonedSvg);
            
            // Show modal
            previewModal.classList.add('active');
            document.body.style.overflow = 'hidden';
        });
    });

    const closePreview = () => {
        previewModal.classList.remove('active');
        document.body.style.overflow = 'auto';
    };

    closePreviewBtn.addEventListener('click', closePreview);
    if (previewModalOverlay) {
        previewModalOverlay.addEventListener('click', closePreview);
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && previewModal.classList.contains('active')) {
            closePreview();
        }
    });
}

observer.observe(document.body, {
    childList: true,
    subtree: true
});
