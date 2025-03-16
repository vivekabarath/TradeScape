import os
import json
import yfinance as yf
import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import signal
from plotly.subplots import make_subplots
import base64
import socket
import psutil
import time
import subprocess
import webbrowser

# --------------------------
# Config file functions
# --------------------------
CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "data_source": "yahoo",
        "stock": "AAPL",
        "time_period": "6mo",
        "interval": "1d",
        "chart_type": "candlestick",
        "extended_hours": [],
        "indicators": ["ma"],
        "yaxis_position": "both",
        "bg_color": "white",
        "yaxis_dtick": 10,
        "auto_refresh": ["enabled"],
        "notes": "",
        "graph_state": {},
        "shapes": []
    }

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

# --------------------------
# Data classes
# --------------------------
class StockData:
    """Fetch and process stock market data from Yahoo Finance."""
    def __init__(self, ticker, period="6mo", interval="1d", extended_hours=False):
        self.ticker = ticker
        self.period = period
        self.interval = interval
        self.extended_hours = extended_hours
        self.data = None
        self.fetch_data()
    def fetch_data(self):
        stock = yf.Ticker(self.ticker)
        self.data = stock.history(period=self.period, interval=self.interval, prepost=self.extended_hours)
        self.data.index = pd.to_datetime(self.data.index, errors='coerce')
        if hasattr(self.data.index, 'tz_localize'):
            self.data.index = self.data.index.tz_localize(None)
    def calculate_moving_averages(self, short_window=20, long_window=50):
        self.data['SMA_Short'] = self.data['Close'].rolling(window=short_window).mean()
        self.data['SMA_Long'] = self.data['Close'].rolling(window=long_window).mean()
    def calculate_bollinger_bands(self, window=20, std_factor=2):
        self.data['SMA'] = self.data['Close'].rolling(window=window).mean()
        self.data['UpperBand'] = self.data['SMA'] + (self.data['Close'].rolling(window=window).std() * std_factor)
        self.data['LowerBand'] = self.data['SMA'] - (self.data['Close'].rolling(window=window).std() * std_factor)
    def calculate_rsi(self, window=14):
        delta = self.data['Close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=window).mean()
        avg_loss = loss.rolling(window=window).mean()
        rs = avg_gain / avg_loss
        self.data['RSI'] = 100 - (100 / (1 + rs))
    def calculate_macd(self):
        ema12 = self.data['Close'].ewm(span=12, adjust=False).mean()
        ema26 = self.data['Close'].ewm(span=26, adjust=False).mean()
        self.data['MACD'] = ema12 - ema26
        self.data['MACD_Signal'] = self.data['MACD'].ewm(span=9, adjust=False).mean()
    def calculate_average_line(self):
        return self.data['Close'].mean()

class StockDataAlphaVantage:
    """Fetch and process stock market data from Alpha Vantage."""
    def __init__(self, ticker, interval="1d"):
        self.ticker = ticker
        self.interval = interval
        self.data = None
        self.fetch_data()
    def fetch_data(self):
        from alpha_vantage.timeseries import TimeSeries
        api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")
        ts = TimeSeries(key=api_key, output_format='pandas')
        if self.interval in ["5m", "10m", "1h"]:
            if self.interval == "5m":
                interval_str = "5min"
            elif self.interval == "10m":
                interval_str = "15min"
            elif self.interval == "1h":
                interval_str = "60min"
            data, _ = ts.get_intraday(symbol=self.ticker, interval=interval_str, outputsize='full')
        elif self.interval == "1d":
            data, _ = ts.get_daily(symbol=self.ticker, outputsize='full')
        elif self.interval == "1wk":
            data, _ = ts.get_weekly(symbol=self.ticker)
        elif self.interval == "1mo":
            data, _ = ts.get_monthly(symbol=self.ticker)
        else:
            data, _ = ts.get_daily(symbol=self.ticker, outputsize='full')
        self.data = data
        self.data.rename(columns={
            '1. open': 'Open',
            '2. high': 'High',
            '3. low': 'Low',
            '4. close': 'Close',
            '5. volume': 'Volume'
        }, inplace=True)
        self.data.index = pd.to_datetime(self.data.index, errors='coerce')
        if hasattr(self.data.index, 'tz_localize'):
            self.data.index = self.data.index.tz_localize(None)
    def calculate_moving_averages(self, short_window=20, long_window=50):
        self.data['SMA_Short'] = self.data['Close'].rolling(window=short_window).mean()
        self.data['SMA_Long'] = self.data['Close'].rolling(window=long_window).mean()
    def calculate_bollinger_bands(self, window=20, std_factor=2):
        self.data['SMA'] = self.data['Close'].rolling(window=window).mean()
        self.data['UpperBand'] = self.data['SMA'] + (self.data['Close'].rolling(window=window).std() * std_factor)
        self.data['LowerBand'] = self.data['SMA'] - (self.data['Close'].rolling(window=window).std() * std_factor)
    def calculate_rsi(self, window=14):
        delta = self.data['Close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=window).mean()
        avg_loss = loss.rolling(window=window).mean()
        rs = avg_gain / avg_loss
        self.data['RSI'] = 100 - (100 / (1 + rs))
    def calculate_macd(self):
        ema12 = self.data['Close'].ewm(span=12, adjust=False).mean()
        ema26 = self.data['Close'].ewm(span=26, adjust=False).mean()
        self.data['MACD'] = ema12 - ema26
        self.data['MACD_Signal'] = self.data['MACD'].ewm(span=9, adjust=False).mean()
    def calculate_average_line(self):
        return self.data['Close'].mean()

# --------------------------
# Main Dash App Class
# --------------------------
class StockAnalysisApp:
    def __init__(self):
        self.config = load_config()
        self.app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
        self.available_stocks = ["AAPL", "TSLA", "MSFT", "GOOGL", "AMZN", "NVDA"]
        self.setup_layout()
        self.setup_callbacks()
        self.register_signal_handlers()
    def setup_layout(self):
        self.app.layout = dbc.Container([
            html.H1("Stock Analysis Dashboard", className="text-center my-4"),
            dbc.Row([
                dbc.Col(
                    dbc.Card([
                        dbc.CardHeader("Data Settings"),
                        dbc.CardBody([
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Data Source:"),
                                    dcc.Dropdown(
                                        id="data-source",
                                        options=[
                                            {"label": "Yahoo Finance", "value": "yahoo"},
                                            {"label": "Alpha Vantage", "value": "alpha_vantage"}
                                        ],
                                        value=self.config.get("data_source", "yahoo"),
                                        clearable=False
                                    )
                                ], width=6),
                                dbc.Col([
                                    html.Label("Stock:"),
                                    dcc.Dropdown(
                                        id="stock-dropdown",
                                        options=[{"label": s, "value": s} for s in self.available_stocks],
                                        value=self.config.get("stock", "AAPL"),
                                        clearable=False
                                    )
                                ], width=6)
                            ], className="mb-2"),
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Time Period:"),
                                    dcc.Dropdown(
                                        id="time-period",
                                        options=[
                                            {"label": "1 Day", "value": "1d"},
                                            {"label": "5 Days", "value": "5d"},
                                            {"label": "1 Week", "value": "1wk"},
                                            {"label": "1 Month", "value": "1mo"},
                                            {"label": "3 Months", "value": "3mo"},
                                            {"label": "6 Months", "value": "6mo"},
                                            {"label": "1 Year", "value": "1y"},
                                            {"label": "5 Years", "value": "5y"},
                                            {"label": "Max", "value": "max"}
                                        ],
                                        value=self.config.get("time_period", "6mo"),
                                        clearable=False
                                    )
                                ], width=6),
                                dbc.Col([
                                    html.Label("Interval:"),
                                    dcc.Dropdown(
                                        id="interval",
                                        options=[
                                            {"label": "5 Minutes", "value": "5m"},
                                            {"label": "10 Minutes", "value": "10m"},
                                            {"label": "1 Hour", "value": "1h"},
                                            {"label": "Daily", "value": "1d"},
                                            {"label": "Weekly", "value": "1wk"},
                                            {"label": "Monthly", "value": "1mo"},
                                        ],
                                        value=self.config.get("interval", "1d"),
                                        clearable=False
                                    )
                                ], width=6)
                            ])
                        ])
                    ]),
                    width=6
                ),
                dbc.Col(
                    dbc.Card([
                        dbc.CardHeader("Display Settings"),
                        dbc.CardBody([
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Chart Type:"),
                                    dcc.Dropdown(
                                        id="chart-type",
                                        options=[
                                            {"label": "Candlestick", "value": "candlestick"},
                                            {"label": "Bar Chart", "value": "bar"},
                                            {"label": "Line Chart", "value": "line"},
                                            {"label": "Area Chart", "value": "area"},
                                        ],
                                        value=self.config.get("chart_type", "candlestick"),
                                        clearable=False
                                    )
                                ], width=6),
                                dbc.Col([
                                    html.Label("Extended Hours (Yahoo):"),
                                    dcc.Checklist(
                                        id="extended-hours",
                                        options=[{"label": "Yes", "value": "extended"}],
                                        value=self.config.get("extended_hours", [])
                                    )
                                ], width=6)
                            ], className="mb-2"),
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Indicators:"),
                                    dcc.Checklist(
                                        id="indicators",
                                        options=[
                                            {"label": "Moving Averages", "value": "ma"},
                                            {"label": "Bollinger Bands", "value": "bb"},
                                            {"label": "RSI", "value": "rsi"},
                                            {"label": "MACD", "value": "macd"},
                                            {"label": "Average Line", "value": "avg"},
                                        ],
                                        value=self.config.get("indicators", ["ma"]),
                                        inline=True
                                    )
                                ])
                            ]),
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Y-Axis Position:"),
                                    dcc.RadioItems(
                                        id="yaxis-position",
                                        options=[
                                            {"label": "Left", "value": "left"},
                                            {"label": "Right", "value": "right"},
                                            {"label": "Both", "value": "both"},
                                        ],
                                        value=self.config.get("yaxis_position", "both"),
                                        inline=True
                                    )
                                ], width=6),
                                dbc.Col([
                                    html.Label("Background Color:"),
                                    dcc.Dropdown(
                                        id="bg-color",
                                        options=[
                                            {"label": "White", "value": "white"},
                                            {"label": "Light Gray", "value": "#f2f2f2"},
                                            {"label": "Dark Mode", "value": "#1e1e1e"},
                                        ],
                                        value=self.config.get("bg_color", "white"),
                                        clearable=False
                                    )
                                ], width=6)
                            ]),
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Y-Axis Tick Interval:"),
                                    dcc.Slider(
                                        id="yaxis-tick-slider",
                                        min=1,
                                        max=100,
                                        step=1,
                                        value=self.config.get("yaxis_dtick", 10),
                                        marks={i: str(i) for i in range(1,101,10)}
                                    )
                                ], width=12)
                            ]),
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Auto Refresh:"),
                                    dcc.Checklist(
                                        id="auto-refresh-check",
                                        options=[{"label": "Enabled", "value": "enabled"}],
                                        value=self.config.get("auto_refresh", ["enabled"])
                                    )
                                ], width=12)
                            ])
                        ])
                    ]),
                    width=6
                )
            ], className="mb-4"),
            dbc.Card([
                dbc.CardHeader("Shape Management"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col(html.Label("Select Shape to Delete:"), width=3),
                        dbc.Col(dcc.Dropdown(id="shape-selector", options=[], multi=False), width=5),
                        dbc.Col(dbc.Button("Delete Selected Shape", id="delete-shape-btn", color="danger"), width=2),
                        dbc.Col(dbc.Button("Clear All Shapes", id="clear-shapes-btn", color="warning"), width=2),
                    ])
                ])
            ], className="mb-4"),
            dbc.Card([
                dbc.CardHeader("Work Management"),
                dbc.CardBody([
                    html.Label("Notes:"),
                    dcc.Textarea(
                        id="notes-textarea",
                        value=self.config.get("notes", ""),
                        style={"width": "100%", "height": "150px"}
                    ),
                    dbc.Row([
                        dbc.Col(dbc.Button("Save Work", id="save-work-btn", color="primary"), width=3),
                        dbc.Col(dcc.Download(id="download-work"), width=3),
                        dbc.Col(dcc.Upload(
                            id="upload-work",
                            children=html.Div("Drag and Drop or Click to Upload Work"),
                            style={
                                "width": "100%",
                                "height": "40px",
                                "lineHeight": "40px",
                                "borderWidth": "1px",
                                "borderStyle": "dashed",
                                "borderRadius": "5px",
                                "textAlign": "center",
                                "margin": "10px"
                            }
                        ), width=6)
                    ])
                ])
            ], className="mb-4"),
            dcc.Store(id="shapes-store", data=self.config.get("shapes", [])),
            dcc.Store(id="graph-state", data=self.config.get("graph_state", {})),
            dcc.Interval(id="interval-component", interval=300000, n_intervals=0),  # 5 minutes auto-refresh
            dbc.Card([
                dbc.CardHeader("Graph"),
                dbc.CardBody(
                    html.Div(
                        dcc.Graph(
                            id="stock-graph",
                            config={
                                "modeBarButtonsToAdd": [
                                    "drawline", "drawopenpath", "drawclosedpath",
                                    "drawcircle", "drawrect", "eraseshape"
                                ],
                                "scrollZoom": True
                            },
                            style={"width": "100%", "height": "100%"}
                        ),
                        style={
                            "resize": "both",
                            "overflow": "auto",
                            "border": "2px dashed #ccc",
                            "padding": "10px",
                            "minWidth": "300px",
                            "minHeight": "300px",
                            "width": "100%",
                            "height": "600px"
                        }
                    )
                )
            ])
        ], fluid=True)
    def setup_callbacks(self):
        # Combined callback to update shapes-store and graph-state from relayout, delete, or clear actions.
        @self.app.callback(
            [Output("shapes-store", "data", allow_duplicate=True),
             Output("graph-state", "data", allow_duplicate=True)],
            [Input("stock-graph", "relayoutData"),
             Input("delete-shape-btn", "n_clicks"),
             Input("clear-shapes-btn", "n_clicks")],
            [State("shape-selector", "value"),
             State("shapes-store", "data"),
             State("graph-state", "data")],
            prevent_initial_call="initial_duplicate"
        )
        def update_graph_and_shapes(relayoutData, delete_click, clear_click, selected_shape, current_shapes, current_graph_state):
            ctx = callback_context
            new_graph_state = current_graph_state
            if ctx.triggered:
                trigger = ctx.triggered[0]["prop_id"]
                if "stock-graph.relayoutData" in trigger:
                    if relayoutData:
                        if "shapes" in relayoutData:
                            current_shapes = relayoutData["shapes"]
                        new_graph_state = relayoutData
                elif "delete-shape-btn.n_clicks" in trigger:
                    if delete_click and selected_shape is not None and current_shapes:
                        idx = int(selected_shape)
                        current_shapes = [s for i, s in enumerate(current_shapes) if i != idx]
                elif "clear-shapes-btn.n_clicks" in trigger:
                    if clear_click:
                        current_shapes = []
            return current_shapes, new_graph_state

        # Callback to update shape-selector options.
        @self.app.callback(
            Output("shape-selector", "options", allow_duplicate=True),
            Input("shapes-store", "data"),
            prevent_initial_call="initial_duplicate"
        )
        def update_shape_selector(shapes_data):
            if shapes_data:
                options = []
                for i, shape in enumerate(shapes_data):
                    shape_type = shape.get("type", "unknown")
                    options.append({"label": f"Shape {i} ({shape_type})", "value": str(i)})
                return options
            return []

        # Callback for saving work (download current config, notes, graph state, and shapes).
        @self.app.callback(
            Output("download-work", "data"),
            Input("save-work-btn", "n_clicks"),
            [State("notes-textarea", "value"),
             State("graph-state", "data"),
             State("shapes-store", "data")],
            prevent_initial_call=True
        )
        def save_work(n_clicks, notes, graph_state, shapes_data):
            current_config = load_config()
            current_config["notes"] = notes
            current_config["graph_state"] = graph_state
            current_config["shapes"] = shapes_data
            return dcc.send_string(json.dumps(current_config, indent=4), filename="saved_work.json")

        # Callback for loading work (update controls, graph state, and shapes with uploaded config).
        @self.app.callback(
            [Output("notes-textarea", "value"),
             Output("data-source", "value"),
             Output("stock-dropdown", "value"),
             Output("time-period", "value"),
             Output("interval", "value"),
             Output("chart-type", "value"),
             Output("indicators", "value"),
             Output("yaxis-position", "value"),
             Output("bg-color", "value"),
             Output("yaxis-tick-slider", "value"),
             Output("auto-refresh-check", "value"),
             Output("graph-state", "data", allow_duplicate=True),
             Output("shapes-store", "data", allow_duplicate=True)],
            Input("upload-work", "contents"),
            State("upload-work", "filename"),
            prevent_initial_call="initial_duplicate"
        )
        def load_work(contents, filename):
            if contents is not None:
                content_type, content_string = contents.split(',')
                try:
                    decoded = base64.b64decode(content_string)
                    loaded_config = json.loads(decoded)
                except Exception as e:
                    return dash.no_update
                return (
                    loaded_config.get("notes", ""),
                    loaded_config.get("data_source", "yahoo"),
                    loaded_config.get("stock", "AAPL"),
                    loaded_config.get("time_period", "6mo"),
                    loaded_config.get("interval", "1d"),
                    loaded_config.get("chart_type", "candlestick"),
                    loaded_config.get("indicators", ["ma"]),
                    loaded_config.get("yaxis_position", "both"),
                    loaded_config.get("bg_color", "white"),
                    loaded_config.get("yaxis_dtick", 10),
                    loaded_config.get("auto_refresh", ["enabled"]),
                    loaded_config.get("graph_state", {}),
                    loaded_config.get("shapes", [])
                )
            return dash.no_update

        # Main chart update callback with uirevision to preserve pan/zoom.
        @self.app.callback(
            Output("stock-graph", "figure"),
            [Input("interval-component", "n_intervals"),
             Input("data-source", "value"),
             Input("stock-dropdown", "value"),
             Input("time-period", "value"),
             Input("interval", "value"),
             Input("chart-type", "value"),
             Input("indicators", "value"),
             Input("yaxis-position", "value"),
             Input("bg-color", "value"),
             Input("extended-hours", "value"),
             Input("yaxis-tick-slider", "value"),
             Input("shapes-store", "data"),
             Input("auto-refresh-check", "value")]
        )
        def update_chart(n_intervals, data_source, stock_symbol, time_period, interval_value,
                         chart_type, indicators, yaxis_position, bg_color, extended_hours,
                         yaxis_dtick, shapes_data, auto_refresh):
            triggers = callback_context.triggered
            only_interval = all("interval-component.n_intervals" in t["prop_id"] for t in triggers)
            if only_interval and "enabled" not in auto_refresh:
                return dash.no_update

            config = {
                "data_source": data_source,
                "stock": stock_symbol,
                "time_period": time_period,
                "interval": interval_value,
                "chart_type": chart_type,
                "extended_hours": extended_hours,
                "indicators": indicators,
                "yaxis_position": yaxis_position,
                "bg_color": bg_color,
                "yaxis_dtick": yaxis_dtick,
                "auto_refresh": auto_refresh
            }
            save_config(config)
            ext_hours = "extended" in extended_hours
            if data_source == "yahoo":
                stock_data = StockData(stock_symbol, period=time_period, interval=interval_value, extended_hours=ext_hours)
            elif data_source == "alpha_vantage":
                try:
                    stock_data = StockDataAlphaVantage(stock_symbol, interval=interval_value)
                except Exception as e:
                    return go.Figure(data=[], layout=go.Layout(title=f"Error fetching data: {e}"))
            else:
                stock_data = StockData(stock_symbol, period=time_period, interval=interval_value, extended_hours=ext_hours)
            if "ma" in indicators:
                stock_data.calculate_moving_averages()
            if "bb" in indicators:
                stock_data.calculate_bollinger_bands()
            extra_rows = 0
            rsi_row = None
            macd_row = None
            if "rsi" in indicators:
                extra_rows += 1
                rsi_row = 2
            if "macd" in indicators:
                extra_rows += 1
                macd_row = 2 if rsi_row is None else 3
            total_rows = 1 + extra_rows
            subplot_titles = ["Price Chart"]
            if rsi_row:
                subplot_titles.append("RSI")
            if macd_row:
                subplot_titles.append("MACD")
            fig = make_subplots(rows=total_rows, cols=1, shared_xaxes=True,
                                vertical_spacing=0.03, subplot_titles=subplot_titles)
            if chart_type == "candlestick":
                fig.add_trace(go.Candlestick(
                    x=stock_data.data.index,
                    open=stock_data.data['Open'],
                    high=stock_data.data['High'],
                    low=stock_data.data['Low'],
                    close=stock_data.data['Close'],
                    name="Candlestick",
                    increasing_line_color='green',
                    decreasing_line_color='red'
                ), row=1, col=1)
            elif chart_type == "bar":
                fig.add_trace(go.Bar(
                    x=stock_data.data.index,
                    y=stock_data.data['Close'],
                    name="Bar Chart"
                ), row=1, col=1)
            elif chart_type == "line":
                fig.add_trace(go.Scatter(
                    x=stock_data.data.index,
                    y=stock_data.data['Close'],
                    mode='lines',
                    name="Line Chart",
                    line=dict(width=2, shape="linear")
                ), row=1, col=1)
            elif chart_type == "area":
                fig.add_trace(go.Scatter(
                    x=stock_data.data.index,
                    y=stock_data.data['Close'],
                    mode='lines',
                    fill='tozeroy',
                    name="Area Chart",
                    line=dict(width=2, shape="linear")
                ), row=1, col=1)
            if "ma" in indicators:
                fig.add_trace(go.Scatter(
                    x=stock_data.data.index,
                    y=stock_data.data.get('SMA_Short', []),
                    mode='lines',
                    name="Short SMA",
                    line=dict(color="blue", dash="dot", width=2, shape="linear")
                ), row=1, col=1)
                fig.add_trace(go.Scatter(
                    x=stock_data.data.index,
                    y=stock_data.data.get('SMA_Long', []),
                    mode='lines',
                    name="Long SMA",
                    line=dict(color="orange", dash="dot", width=2, shape="linear")
                ), row=1, col=1)
            if "bb" in indicators:
                fig.add_trace(go.Scatter(
                    x=stock_data.data.index,
                    y=stock_data.data.get('UpperBand', []),
                    mode='lines',
                    name="Upper Bollinger Band",
                    line=dict(color="purple", dash="dot", width=2, shape="linear")
                ), row=1, col=1)
                fig.add_trace(go.Scatter(
                    x=stock_data.data.index,
                    y=stock_data.data.get('LowerBand', []),
                    mode='lines',
                    name="Lower Bollinger Band",
                    line=dict(color="purple", dash="dot", width=2, shape="linear")
                ), row=1, col=1)
            if "avg" in indicators:
                avg_val = stock_data.calculate_average_line()
                fig.add_hline(y=avg_val, line_dash="dash", line_color="black", annotation_text="Average", row=1, col=1)
            if "rsi" in indicators:
                stock_data.calculate_rsi()
                fig.add_trace(go.Scatter(
                    x=stock_data.data.index,
                    y=stock_data.data.get('RSI', []),
                    mode='lines',
                    name="RSI",
                    line=dict(color="magenta", width=2, shape="linear")
                ), row=rsi_row, col=1)
                fig.update_yaxes(range=[0, 100], row=rsi_row, col=1)
            if "macd" in indicators:
                stock_data.calculate_macd()
                fig.add_trace(go.Scatter(
                    x=stock_data.data.index,
                    y=stock_data.data.get('MACD', []),
                    mode='lines',
                    name="MACD",
                    line=dict(color="brown", width=2, shape="linear")
                ), row=macd_row, col=1)
                fig.add_trace(go.Scatter(
                    x=stock_data.data.index,
                    y=stock_data.data.get('MACD_Signal', []),
                    mode='lines',
                    name="MACD Signal",
                    line=dict(color="grey", dash="dot", width=2, shape="linear")
                ), row=macd_row, col=1)
            yaxis_settings = dict(title="Stock Price", side="left", dtick=yaxis_dtick)
            layout_update = dict(
                xaxis_title="Date and Time",
                xaxis=dict(type='date', tickformat="%Y-%m-%d %H:%M"),
                plot_bgcolor=bg_color,
                uirevision="static"
            )
            if yaxis_position == "right":
                yaxis_settings["side"] = "right"
                layout_update["yaxis"] = yaxis_settings
            elif yaxis_position == "both":
                layout_update["yaxis"] = yaxis_settings
                layout_update["yaxis2"] = dict(title="Stock Price", side="right", overlaying="y", showgrid=False, dtick=yaxis_dtick)
            else:
                layout_update["yaxis"] = yaxis_settings
            stored_graph_state = self.config.get("graph_state", {})
            if stored_graph_state:
                layout_update.update(stored_graph_state)
            fig.update_layout(**layout_update)
            fig.update_layout(title=f"{stock_symbol} - {time_period} @ {interval_value}", showlegend=True)
            if shapes_data:
                # Ensure drawn shapes are crisp and sharp.
                for shape in shapes_data:
                    if "line" not in shape:
                        shape["line"] = {}
                    shape["line"]["width"] = 2
                fig.update_layout(shapes=shapes_data)
            return fig

    def register_signal_handlers(self):
        def stop_server(signal_received, frame):
            print("\nStopping Dash server...")
            os._exit(0)
        signal.signal(signal.SIGINT, stop_server)
        signal.signal(signal.SIGTERM, stop_server)

    def run(self, port=8081):
        self.app.run_server(debug=True, port=port)

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def kill_all_processes_on_port(port):
    for conn in psutil.net_connections():
        if conn.laddr.port == port and conn.pid and conn.pid != os.getpid():
            try:
                p = psutil.Process(conn.pid)
                if os.geteuid() != 0:
                    print(f"Requesting sudo to kill process {p.name()} (PID: {p.pid}) using port {port}.")
                    subprocess.run(['sudo', 'kill', '-9', str(p.pid)], check=True)
                else:
                    p.kill()
                print(f"Process {p.name()} (PID: {p.pid}) killed.")
            except Exception as e:
                print(f"Failed to kill process {p.name()} (PID: {p.pid}): {e}")

def wait_for_port_to_free(port, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        if not is_port_in_use(port):
            return True
        time.sleep(1)
    return False

if __name__ == "__main__":
    default_port = 8081
    if is_port_in_use(default_port):
        print(f"Port {default_port} is in use. Attempting to kill all processes using it with sudo privileges...")
        kill_all_processes_on_port(default_port)
        if wait_for_port_to_free(default_port, timeout=10):
            print(f"Port {default_port} is now free. Continuing...")
        else:
            default_port = int(input(f"Port {default_port} is still in use. Enter an alternative port number: "))
    url = f"http://127.0.0.1:{default_port}/"
    print(f"Opening {url} in the default web browser...")
    webbrowser.open(url)
    app = StockAnalysisApp()
    app.run(port=default_port)
