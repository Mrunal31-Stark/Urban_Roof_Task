const pipelineContainer = document.getElementById('pipeline');
const messageEl = document.getElementById('message');
const reportEl = document.getElementById('report');

const steps = [
  'Extracting Text',
  'Detecting Observations',
  'Checking Conflicts',
  'Building Report',
];

function renderSteps(active = -1, done = -1) {
  pipelineContainer.innerHTML = '';
  steps.forEach((step, idx) => {
    const div = document.createElement('div');
    div.className = 'step';
    if (idx <= done) div.classList.add('done');
    else if (idx === active) div.classList.add('active');
    div.textContent = step;
    pipelineContainer.appendChild(div);
  });
}

function badgeClass(level) {
  const l = (level || '').toLowerCase();
  if (l === 'high') return 'badge-high';
  if (l === 'medium') return 'badge-medium';
  return 'badge-low';
}

function asList(items) {
  return `<ul>${items.map(i => `<li>${i}</li>`).join('')}</ul>`;
}

function renderReport(payload, reportId, downloads) {
  const report = payload.report;
  reportEl.classList.remove('hidden');

  document.getElementById('jsonDownload').href = downloads.json;
  document.getElementById('pdfDownload').href = downloads.pdf;

  document.getElementById('summary').innerHTML = `<h3>Property Issue Summary</h3>${asList(report.property_issue_summary)}`;
  document.getElementById('severity').innerHTML = `
    <h3>Severity Assessment</h3>
    <p><span class="badge ${badgeClass(report.severity_assessment.level)}">${report.severity_assessment.level}</span></p>
    <p>${report.severity_assessment.reasoning}</p>
    <p class="small">Confidence: ${JSON.stringify(report.confidence_scores)}</p>
  `;

  document.getElementById('conflicts').innerHTML = `<h3>Conflicts</h3>${report.conflicts.map(c => `<p class="conflict">${c}</p>`).join('')}`;

  const areaHtml = Object.entries(report.area_wise_observations).map(([area, lines]) => (
    `<details class="accordion"><summary>${area}</summary>${asList(lines)}</details>`
  )).join('');
  document.getElementById('areas').innerHTML = `<h3>Area-wise Observations</h3>${areaHtml}`;

  document.getElementById('missing').innerHTML = `<h3>Missing Information</h3>${asList(report.missing_or_unclear_information)}`;
  document.getElementById('history').innerHTML = `<p class="small">Report ID: ${reportId}</p>`;
}

async function fetchHistory() {
  const res = await fetch('/api/history');
  if (!res.ok) return;
  const data = await res.json();
  const history = data.items || [];
  if (!history.length) return;

  const historyHtml = `<h3>Recent Reports</h3><ul>${history
    .map(item => `<li>${item.id} — ${item.severity} (${item.created_at})</li>`)
    .join('')}</ul>`;
  document.getElementById('history').insertAdjacentHTML('beforeend', historyHtml);
}

document.getElementById('uploadForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.currentTarget;
  const data = new FormData(form);

  messageEl.textContent = 'Uploading files...';
  renderSteps(0, -1);

  for (let i = 0; i < steps.length; i += 1) {
    renderSteps(i, i - 1);
    await new Promise(r => setTimeout(r, 240));
  }

  const res = await fetch('/api/upload', { method: 'POST', body: data });
  if (!res.ok) {
    const err = await res.json();
    messageEl.textContent = err.error || 'Processing failed.';
    return;
  }

  const payload = await res.json();
  renderSteps(-1, steps.length - 1);
  messageEl.textContent = 'DDR generated successfully.';
  renderReport(payload, payload.report_id, payload.downloads);
  await fetchHistory();
});

renderSteps();
fetchHistory();
