const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const v8 = require('v8');

// Create directory for heap snapshots if it doesn't exist
const snapshotsDir = path.join(__dirname, 'snapshots');
if (!fs.existsSync(snapshotsDir)) {
  fs.mkdirSync(snapshotsDir, { recursive: true });
}

// Start server with inspector to allow heap snapshots
console.log('Starting Tetristributed server with memory profiling...');
const serverProcess = require('child_process').spawn('node', [
  '--inspect',
  path.join(__dirname, '../../src/server.js')
], {
  stdio: 'inherit'
});

// Give server time to start
console.log('Waiting for server to initialize...');
setTimeout(() => {
  console.log('Server initialized, beginning load test...');
  
  // Take initial heap snapshot
  takeHeapSnapshot('before-load');
  
  // Record memory usage over time
  const memoryUsage = [];
  const memoryInterval = setInterval(() => {
    const usage = process.memoryUsage();
    const timestamp = new Date().toISOString();
    memoryUsage.push({
      timestamp,
      rss: usage.rss / (1024 * 1024),  // Convert to MB
      heapTotal: usage.heapTotal / (1024 * 1024),
      heapUsed: usage.heapUsed / (1024 * 1024),
      external: usage.external / (1024 * 1024),
      arrayBuffers: usage.arrayBuffers ? usage.arrayBuffers / (1024 * 1024) : 0
    });
    
    console.log(`Memory usage at ${timestamp}: ${Math.round(usage.heapUsed / (1024 * 1024))} MB`);
  }, 5000); // Every 5 seconds
  
  // Run load test
  try {
    console.log('Starting Artillery load test...');
    execSync('npx artillery run basic-load.yml', { 
      stdio: 'inherit',
      cwd: __dirname
    });
  } catch (e) {
    console.error('Load test failed:', e);
  }
  
  // Take post-test heap snapshot
  takeHeapSnapshot('after-load');
  
  // Save memory usage data
  clearInterval(memoryInterval);
  fs.writeFileSync(
    path.join(snapshotsDir, `memory-usage-${Date.now()}.json`), 
    JSON.stringify(memoryUsage, null, 2)
  );
  
  // Generate a simple HTML report
  generateMemoryReport(memoryUsage);
  
  // Shutdown server
  console.log('Testing complete, shutting down server...');
  serverProcess.kill();
}, 5000);

function takeHeapSnapshot(label) {
  const snapshotPath = path.join(snapshotsDir, `heap-${label}-${Date.now()}.heapsnapshot`);
  
  try {
    console.log(`Taking heap snapshot: ${label}...`);
    const snapshot = v8.getHeapSnapshot();
    fs.writeFileSync(snapshotPath, snapshot);
    console.log(`Heap snapshot saved to ${snapshotPath}`);
  } catch (error) {
    console.error(`Failed to take heap snapshot: ${error.message}`);
  }
}

function generateMemoryReport(memoryData) {
  const reportPath = path.join(snapshotsDir, `memory-report-${Date.now()}.html`);
  
  const chartData = {
    labels: memoryData.map(entry => {
      const date = new Date(entry.timestamp);
      return `${date.getHours()}:${date.getMinutes()}:${date.getSeconds()}`;
    }),
    heapUsed: memoryData.map(entry => entry.heapUsed),
    rss: memoryData.map(entry => entry.rss),
    heapTotal: memoryData.map(entry => entry.heapTotal)
  };
  
  const html = `
<!DOCTYPE html>
<html>
<head>
  <title>Tetristributed Memory Usage Report</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; }
    .chart-container { width: 800px; height: 400px; margin-bottom: 30px; }
    table { border-collapse: collapse; width: 100%; margin-top: 20px; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    th { background-color: #f2f2f2; }
    tr:nth-child(even) { background-color: #f9f9f9; }
  </style>
</head>
<body>
  <h1>Tetristributed Memory Usage Report</h1>
  <div class="chart-container">
    <canvas id="memoryChart"></canvas>
  </div>
  
  <h2>Statistics</h2>
  <table>
    <tr>
      <th>Metric</th>
      <th>Min (MB)</th>
      <th>Max (MB)</th>
      <th>Avg (MB)</th>
    </tr>
    <tr>
      <td>Heap Used</td>
      <td>${Math.min(...chartData.heapUsed).toFixed(2)}</td>
      <td>${Math.max(...chartData.heapUsed).toFixed(2)}</td>
      <td>${(chartData.heapUsed.reduce((a, b) => a + b, 0) / chartData.heapUsed.length).toFixed(2)}</td>
    </tr>
    <tr>
      <td>RSS</td>
      <td>${Math.min(...chartData.rss).toFixed(2)}</td>
      <td>${Math.max(...chartData.rss).toFixed(2)}</td>
      <td>${(chartData.rss.reduce((a, b) => a + b, 0) / chartData.rss.length).toFixed(2)}</td>
    </tr>
    <tr>
      <td>Heap Total</td>
      <td>${Math.min(...chartData.heapTotal).toFixed(2)}</td>
      <td>${Math.max(...chartData.heapTotal).toFixed(2)}</td>
      <td>${(chartData.heapTotal.reduce((a, b) => a + b, 0) / chartData.heapTotal.length).toFixed(2)}</td>
    </tr>
  </table>
  
  <h2>Raw Data</h2>
  <table>
    <tr>
      <th>Time</th>
      <th>Heap Used (MB)</th>
      <th>RSS (MB)</th>
      <th>Heap Total (MB)</th>
    </tr>
    ${memoryData.map(entry => `
      <tr>
        <td>${entry.timestamp}</td>
        <td>${entry.heapUsed.toFixed(2)}</td>
        <td>${entry.rss.toFixed(2)}</td>
        <td>${entry.heapTotal.toFixed(2)}</td>
      </tr>
    `).join('')}
  </table>

  <script>
    const ctx = document.getElementById('memoryChart').getContext('2d');
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: ${JSON.stringify(chartData.labels)},
        datasets: [
          {
            label: 'Heap Used (MB)',
            data: ${JSON.stringify(chartData.heapUsed)},
            borderColor: 'rgb(255, 99, 132)',
            tension: 0.1
          },
          {
            label: 'RSS (MB)',
            data: ${JSON.stringify(chartData.rss)},
            borderColor: 'rgb(54, 162, 235)',
            tension: 0.1
          },
          {
            label: 'Heap Total (MB)',
            data: ${JSON.stringify(chartData.heapTotal)},
            borderColor: 'rgb(75, 192, 192)',
            tension: 0.1
          }
        ]
      },
      options: {
        responsive: true,
        scales: {
          y: {
            beginAtZero: true,
            title: {
              display: true,
              text: 'Memory (MB)'
            }
          },
          x: {
            title: {
              display: true,
              text: 'Time'
            }
          }
        }
      }
    });
  </script>
</body>
</html>
  `;
  
  fs.writeFileSync(reportPath, html);
  console.log(`Memory usage report generated: ${reportPath}`);
}