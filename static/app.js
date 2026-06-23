/**
 * DOCUMENTATION VISUALIZATION ASSISTANT - CLIENT SIDE INTERACTIVITY
 */

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initFileUpload();
    initSamples();
    initResultsPanel();
    initGifTimelines();
    initFormLoading();
    initArtifactTools();
    initInsertButtons();
});

// Sample text templates mapping
const SAMPLES = {
    workflow: `# Database Synchronisation Procedure

Overview
This procedure describes how to export user database records and import them into the secondary HMI panel.

Procedure
1. Login to the administration portal and locate the export data menu.
2. Click the 'Export Records' button on the main configuration panel.
3. Select the XML tags format from the drop-down dialog and click Confirm.
4. Wait for the download file window to appear, then save the synchronisation package.
5. Connect the sync cable between the gateway server and the HMI device.
6. Mount device securely and connect to the auxiliary power supply socket.
7. Open the HMI synchronisation manager tab, select import files, and choose the synchronization package.
8. Click the 'Start Sync' button to load all parameters.`,

    architecture: `# Factory Floor System Architecture

Overview
The factory network environment establishes connections between local control networks and remote cloud databases.

System Layout
A main PLC controller connects directly to the local HMI panel. The industrial gateway acts as the firewall connecting the control layer to the cloud server database.

Configuration Details
The connection parameters are structured in JSON format:
{
  "server_ip": "192.168.1.100",
  "port": 8080,
  "plc_id": "PLC_CORE_01",
  "hmi_active": true
}

If security protocol is disabled, the gateway will block all incoming external traffic. Otherwise, it forwards packages securely.`,

    decision: `# Valve Troubleshooting Flow

Overview
Follow this valve safety logic to determine if physical maintenance is required.

Procedure
1) Check the pressure gauge. If the pressure displays a value above 5.0 bar, then check the relief valve status immediately.
2) If the relief valve status light is green, proceed to the secondary vent control.
3) Else, if the light is red, shut down the main power feed.
4) Otherwise, continue normal operations.`,

    summary: `# Industrial Gateway Configuration

Overview
The industrial communication gateway supports cross-protocol data routing between legacy serial devices and cloud-based REST endpoints. This device contains dual ethernet interfaces for subnet isolation and hardware-based encryption.

Device Setup Guidelines
Ensure that all cables are shielded to prevent electromagnetic interference in high-voltage environments. It is recommended to perform a firmware check prior to deploying to live environments.`
};

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
 * Load Sample Texts
 */
function initSamples() {
    const sampleBtns = document.querySelectorAll('.sample-btn');
    const editor = document.querySelector('textarea.editor');
    const textTabBtn = document.querySelector('[data-tab="text"]');

    sampleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const type = btn.dataset.sample;
            if (SAMPLES[type]) {
                // Switch to text tab if not active
                textTabBtn.click();
                editor.value = SAMPLES[type];
                editor.focus();
                
                // Pulse editor for visual feedback
                editor.style.borderColor = 'var(--primary)';
                setTimeout(() => {
                    editor.style.borderColor = 'var(--border-color)';
                }, 800);
            }
        });
    });
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
            securityLevel: 'loose',
            theme: 'dark'
        });
        document.querySelectorAll('.artifact-mermaid-preview').forEach((preview, index) => {
            if (preview.dataset.rendered === 'true') {
                return;
            }
            preview.dataset.rendered = 'true';
            const source = preview.textContent;
            window.mermaid.render(`artifact-preview-${index}`, source).then(({ svg }) => {
                preview.innerHTML = svg;
            }).catch(() => {
                preview.textContent = source;
            });
        });
    }
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
    setTimeout(initInsertButtons, 100);
});

// Also reinit when results are refreshed
const observer = new MutationObserver(() => {
    initDetailsToggle();
    initArtifactTools();
    initInsertButtons();
});

observer.observe(document.body, {
    childList: true,
    subtree: true
});
