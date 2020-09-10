import pickle
from datetime import timedelta, datetime
import pandas as pd
import statsmodels.formula.api as sm
from statsmodels.iolib.summary2 import summary_col
import matplotlib.pyplot as plt
import numpy as np
import historical_data_collection.excel_helpers as excel
import config
import exceptions_library as exception
import fundamental_analysis.macroeconomic_analysis as macro

'''
https://alphaarchitect.com/2011/08/01/how-to-use-the-fama-french-model/
https://www.sciencedirect.com/topics/economics-econometrics-and-finance/capm
https://hackernoon.com/using-capital-asset-pricing-model-capm-versus-black-scholes-model-to-value-stocks-a-how-to-guide-r53032tc
http://content.moneyinstructor.com/948/capm.html
'''


def initialize_factors_dataframe(model: str, portfolio_returns: pd.Series,
                                 benchmark_returns: pd.Series) -> pd.DataFrame:
    time_delta = portfolio_returns.index[1] - portfolio_returns.index[0]
    if time_delta.days == 1:
        period = 'Daily'
    elif time_delta.days == 7:
        period = 'Weekly'
    elif time_delta.days == 30 or time_delta.days == 31:
        period = 'Monthly'
    elif time_delta.days == 365 or time_delta.days == 366:
        period = 'Yearly'
    else:
        raise Exception
    df_factors = excel.read_df_from_csv(path='{}/{}.xlsx'.format(config.FACTORS_DIR_PATH, model),
                                        sheet_name=period)
    date_idx = excel.get_date_index(portfolio_returns.index[0], df_factors.index)
    df_factors = df_factors[date_idx:]

    df_factors['Mkt-RF'] = benchmark_returns - df_factors['RF']  # excess market returns
    df_factors.rename(columns={'Mkt-RF': 'MKT'}, inplace=True)
    portfolio_returns.rename('Returns', inplace=True)
    df_stock_factor = pd.merge(portfolio_returns, df_factors, left_index=True, right_index=True)
    df_stock_factor['XsRet'] = df_stock_factor['Returns'] - df_stock_factor['RF']  # excess portfolio returns
    return df_stock_factor


def plot(df_stock_factor, regression_model):
    plt.plot(df_stock_factor['XsRet'], df_stock_factor['MKT'], 'r.')
    # params[0] is const coef (y-axis intersection), and params[1] is AAPL coeff (correlation coefficient)
    plt.scatter(df_stock_factor['MKT'], df_stock_factor['XsRet'])
    plt.plot(df_stock_factor['MKT'], regression_model.params[0] + regression_model.params[1] * df_stock_factor['MKT'],
             'b', lw=2)
    plt.grid(True)
    plt.axis('tight')
    plt.xlabel('Portfolio Returns')
    plt.ylabel('Market Returns')
    plt.show()
    return plt


'''
The Capital Asset Pricing Model (CAPM) evaluates the required rate of return of an asset relative to 
its sensitivity to risk in the broader financial markets (i.e. systematic risk). 
'''


def capital_asset_pricing_model(portfolio_returns, benchmark_returns):
    df_stock_factor = initialize_factors_dataframe(model='CAPM',
                                                   portfolio_returns=portfolio_returns,
                                                   benchmark_returns=benchmark_returns)
    CAPM = sm.ols(formula='XsRet ~ MKT', data=df_stock_factor).fit(cov_type='HAC', cov_kwds={'maxlags': 1})
    print(CAPM.summary())
    return CAPM


# plot(df_stock_factor=df_stock_factor, regression_model=CAPM)


def fama_french_3_factor_model(portfolio_returns, benchmark_returns):
    df_stock_factor = initialize_factors_dataframe(model='Fama-French 3 Factor',
                                                   portfolio_returns=portfolio_returns,
                                                   benchmark_returns=benchmark_returns)
    FF3 = sm.ols(formula='XsRet ~ MKT + SMB + HML', data=df_stock_factor).fit(cov_type='HAC', cov_kwds={'maxlags': 1})
    print(FF3.summary())
    plot(df_stock_factor=df_stock_factor, regression_model=FF3)
    return FF3


def carhart_4_factor_model(portfolio_returns, benchmark_returns):
    df_stock_factor = initialize_factors_dataframe(model='Carhart 4 Factor',
                                                   portfolio_returns=portfolio_returns,
                                                   benchmark_returns=benchmark_returns)
    CARHART = sm.ols(formula='XsRet ~ MKT + SMB + HML + MOM', data=df_stock_factor).fit(cov_type='HAC',
                                                                                        cov_kwds={'maxlags': 1})
    print(CARHART.summary())
    plot(df_stock_factor=df_stock_factor, regression_model=CARHART)
    return CARHART


def fama_french_5_factor_model(portfolio_returns, benchmark_returns):
    df_stock_factor = initialize_factors_dataframe(model='Fama-French 5 Factor',
                                                   portfolio_returns=portfolio_returns,
                                                   benchmark_returns=benchmark_returns)
    FF5 = sm.ols(formula='XsRet ~ MKT + SMB + HML + RMW + CMA', data=df_stock_factor).fit(cov_type='HAC',
                                                                                          cov_kwds={'maxlags': 1})
    print(FF5.summary())
    plot(df_stock_factor=df_stock_factor, regression_model=FF5)
    return FF5


def factor_dataframe(portfolio_returns, benchmark_returns):
    capm_stats = capital_asset_pricing_model(portfolio_returns=portfolio_returns,
                                             benchmark_returns=benchmark_returns)
    carhart_stats = carhart_4_factor_model(portfolio_returns=portfolio_returns,
                                           benchmark_returns=benchmark_returns)
    ff3_stats = fama_french_3_factor_model(portfolio_returns=portfolio_returns,
                                           benchmark_returns=benchmark_returns)
    ff5_stats = fama_french_5_factor_model(portfolio_returns=portfolio_returns,
                                           benchmark_returns=benchmark_returns)

    # DataFrame with coefficients and t-stats
    results_df = pd.DataFrame({'CAPMcoeff': capm_stats.params, 'CAPMtstat': capm_stats.tvalues,
                               'FF3coeff': ff3_stats.params, 'FF3tstat': ff3_stats.tvalues,
                               'CARHARTcoeff': carhart_stats.params, 'CARHARTstat': carhart_stats.tvalues,
                               'FF5coeff': ff5_stats.params, 'FF5tstat': ff5_stats.tvalues},
                              index=['Intercept', 'MKT', 'SMB', 'HML', 'MOM', 'RMW', 'CMA'])

    dfoutput = summary_col([capm_stats, ff3_stats, carhart_stats, ff5_stats], stars=True, float_format='%0.4f',
                           model_names=['CAPM', 'FF3', 'CARHART', 'FF5'],
                           info_dict={'N': lambda x: "{0:d}".format(int(x.nobs)),
                                      'Adjusted R2': lambda x: "{:.4f}".format(x.rsquared_adj)},
                           regressor_order=['Intercept', 'MKT', 'SMB', 'HML', 'MOM', 'RMW', 'CMA'])
    print(dfoutput)
    return results_df


'''
Wrapper when we need to gather returns data for benchmark and asset, slice, resample, and merge returns before feeding into an asset pricing model
It then calls the appropriate model
Model is 'CAPM', 'Fama-French 3 Factor', 'Carhart 4 Factor', 'Fama-French 5 Factor'
If Portfolio Returns is string, then it's for an asset, we can read from Excel, otherwise it should be a series for a portfolio of assets
Benchmark is by default for Fama French (all NASDAQ, AMEX etc.), otherwise '^GSPC' for S&P500, '^DJI' for Dow Jones Industrial
'''


def asset_pricing_wrapper(model, portfolio, benchmark=None, period='Monthly',
                          from_date=None, to_date=None):
    benchmark_returns, portfolio_returns = excel.slice_resample_merge_returns(portfolio=portfolio, benchmark=benchmark,
                                                                              from_date=from_date, to_date=to_date,
                                                                              period=period)
    if model == 'CAPM':
        return capital_asset_pricing_model(portfolio_returns=portfolio_returns, benchmark_returns=benchmark_returns)
    elif model == 'Fama-French 3 Factor':
        return fama_french_3_factor_model(portfolio_returns=portfolio_returns, benchmark_returns=benchmark_returns)
    elif model == 'Carhart 4 Factor':
        return carhart_4_factor_model(portfolio_returns=portfolio_returns, benchmark_returns=benchmark_returns)
    elif model == 'Fama-French 5 Factor':
        return fama_french_5_factor_model(portfolio_returns=portfolio_returns, benchmark_returns=benchmark_returns)
    else:
        raise exception.InvalidAssetPricingModelException


'''
The Security Market Line (SML) graphically represents the relationship between the asset's return (on y-axis) and systematic risk (or beta, on x-axis).
With E(R_i) = R_f + B_i * (E(R_m) - R_f), the y-intercept of the SML is equal to the risk-free interest rate, while the slope is equal to the market risk premium
Plotting the SML for a market index (i.e. DJIA), individual assets that are correctly priced are plotted on the SML (in the ideal 'Efficient Market Hypothesis' world). 
In real market scenarios, we are able to use the SML graph to determine if an asset being considered for a portfolio offers a reasonable expected return for the risk. 
- If an asset is priced at a point above the SML, it is undervalued, since for a given amount of risk, it yields a higher return. 
- Conversely, an asset priced below the SML is overvalued, since for a given amount of risk, it yields a lower return.
'''


def security_market_line(assets_tickers, from_date=datetime.now() - timedelta(days=3 * 365), to_date=datetime.now(),
                         period='Monthly', benchmark='^DJI'):
    merged_returns = pd.DataFrame()
    for ticker in assets_tickers:
        benchmark_returns, portfolio_returns = excel.slice_resample_merge_returns(portfolio=ticker, benchmark=benchmark,
                                                                                  from_date=from_date, to_date=to_date,
                                                                                  period=period)
        portfolio_returns.rename(ticker, inplace=True)
        if merged_returns.empty:
            merged_returns = pd.concat([benchmark_returns, portfolio_returns], axis=1, join='outer')
            continue
        merged_returns = pd.concat(objs=[merged_returns, portfolio_returns], axis=1, join='outer')

    risk_free_rate = macro.cumulative_risk_free_rate(from_date=from_date, to_date=to_date)
    risk_premium = macro.cumulative_market_premium(from_date=from_date, to_date=to_date)
    x = np.linspace(0, 2.5, 100)
    y = risk_free_rate + x * risk_premium

    fig, ax = plt.subplots(figsize=(10, 10))
    plt.plot(x, y)
    ax.set_xlabel('Betas', fontsize=14)
    ax.set_ylabel('Expected Returns', fontsize=14)
    ax.set_title('Security Market Line', fontsize=18)

    betas = merged_returns.apply(lambda col: capital_asset_pricing_model(portfolio_returns=col,
                                                                         benchmark_returns=merged_returns.iloc[:,
                                                                                           0]).params[1])

    actual_returns = merged_returns.apply(lambda col: (col + 1).cumprod()[-1] - 1)
    assets_tickers.insert(0, benchmark)
    for i, txt in enumerate(assets_tickers):
        ax.annotate(txt, (betas[i], actual_returns[i]), xytext=(10, 10), textcoords='offset points')
        plt.scatter(betas[i], actual_returns[i], marker='x', color='red')
    plt.show()
    print(merged_returns.head())


def security_market_line_wrapper(index: str):
    if index == 'S&P 500':
        with open("{}/sp500_tickers.pickle".format(config.MARKET_TICKERS_DIR_PATH), "rb") as f:
            tickers = pickle.load(f)
        security_market_line(tickers, benchmark='^GSPC')
    elif index == 'DJIA':
        with open("{}/djia30_tickers.pickle".format(config.MARKET_TICKERS_DIR_PATH), "rb") as f:
            tickers = pickle.load(f)
        security_market_line(tickers, benchmark='^DJI')
    elif index == 'Russell 3000':
        with open("{}/russel3000_tickers.pickle".format(config.MARKET_TICKERS_DIR_PATH), "rb") as f:
            tickers = pickle.load(f)
        security_market_line(tickers, benchmark='^RUA')
    elif index == 'NASDAQ':
        with open("{}/nasdaq_df.pickle".format(config.MARKET_TICKERS_DIR_PATH), "rb") as f:
            tickers = pickle.load(f).index
        security_market_line(tickers, benchmark='^IXIC')


if __name__ == '__main__':
    security_market_line_wrapper(index='DJIA')