import pandas as pd


class UploadedSeasonalRevenue(Factor):
    def calculate(self, factors):
        # Data contains only announcement-date PIT signals, no future returns.
        # The supported FileUploadControl must be connected to CodeControl.
        table = pd.read_parquet(upload_path('uploads/seasonal_revenue_pit_daily.parquet'))
        table['date'] = pd.to_datetime(table['date'])
        signal = table.set_index(['date', 'symbol'])['value'].astype(float)
        # Platform index is fixed [date, symbol]. Restrict the uploaded data to
        # the current runtime index; truncation must not alter historical values.
        index = factors['close'].index
        dates = pd.to_datetime(index.get_level_values(0))
        symbols = index.get_level_values(1)
        lookup = pd.MultiIndex.from_arrays([dates, symbols], names=['date', 'symbol'])
        output = signal.reindex(lookup)
        output.index = index
        return output.rename('value')
