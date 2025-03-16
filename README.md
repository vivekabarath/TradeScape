

---

# TradeScape

**TradeScape** is a dynamic, interactive stock analysis dashboard built in Python using Dash and Plotly. It fetches data from Yahoo Finance and Alpha Vantage, provides multiple chart types and technical indicators, and offers extensive features for drawing and managing annotations (shapes) on the graphs. Users can save their entire session (including notes, graph state, and drawn shapes) as a JSON file and reload it later.

## Features

- **Multi-Source Data Retrieval:**  
  Fetches stock data from Yahoo Finance and Alpha Vantage.

- **Versatile Chart Types:**  
  Display stock data as Candlestick, Bar, Line, or Area charts.

- **Technical Indicators:**  
  Overlay Moving Averages, Bollinger Bands, RSI, MACD, and an Average Line on your charts.

- **Interactive Shape Management:**  
  Draw, delete, and clear shapes on the chart. All shapes are rendered with crisp, sharp lines.

- **Session Management:**  
  Save your dashboard configuration—including notes, graph state (pan/zoom), and drawn shapes—as a JSON file. Reload a saved session with a simple upload.

- **Auto-Refresh Toggle:**  
  Enable or disable automatic data refresh.

- **Port Management with Sudo Support:**  
  Before launching, the script checks if the default port (8081) is in use. If so, it attempts to free the port (using sudo if necessary) and opens the app in your default browser.

- **Crisp Visuals:**  
  All chart lines and drawn shapes are configured with a line width of 2 and a linear shape to ensure a sharp, professional appearance.

## Installation

### Prerequisites

- Python 3.12 (or later recommended)
- pip (Python package installer)

### Install Dependencies

Clone the repository and install the required packages using pip:

```bash
git clone <repository_url>
cd <repository_folder>
pip install yfinance dash dash-bootstrap-components plotly pandas numpy alpha_vantage psutil
```

Alternatively, use the provided `requirements.txt` file:

```bash
pip install -r requirements.txt
```

*Sample `requirements.txt`:*

```
yfinance
dash
dash-bootstrap-components
plotly
pandas
numpy
alpha_vantage
psutil
```

## Usage

Run the script from the command line. For example, to launch the dashboard for a specific stock (e.g. NVDA):

```bash
python3 TradeScape.py NVDA
```

### What Happens When You Run It

1. **Port Check:**  
   The script checks if port 8081 is in use. If it is, it automatically attempts to kill conflicting processes (using sudo if not running as root) and waits until the port is free. If the port remains in use after 10 seconds, you'll be prompted to specify an alternative port.

2. **Automatic Browser Launch:**  
   Once the port is free, the script automatically opens the dashboard URL (e.g. `http://127.0.0.1:8081/`) in your default web browser.

3. **Dashboard Interface:**  
   - **Data Settings:** Choose the data source, stock ticker, time period, and data interval.
   - **Display Settings:** Select chart type, technical indicators, and adjust y-axis settings, background color, and auto-refresh options.
   - **Shape Management:** Draw shapes on the chart, delete individual shapes, or clear all shapes.
   - **Work Management:** Write notes and save the entire session (configuration, notes, graph state, shapes) as a JSON file. Reload a saved session using the upload area.
   - **Graph:** The graph is rendered in a resizable container with crisp, sharp lines and preserved pan/zoom settings.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request if you have suggestions, improvements, or bug fixes.


---

*TradeScape* gives you a comprehensive view of the market to help you make informed trading decisions with an intuitive, professional interface. Enjoy exploring your stocks with TradeScape!

---

Feel free to customize this README to better fit your project's details or your personal preferences.
