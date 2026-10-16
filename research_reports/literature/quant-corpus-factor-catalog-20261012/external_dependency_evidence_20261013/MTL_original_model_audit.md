# 多任务动量原作者模型审计

冻结作者版本 3f83a77f4c7996ed8185b8979a42c4372c1d811f；外部模块未导入、未运行。原模型未通过因果复现认证，未把源文献四只ETF的结果当作全A因子回测。

- [MTL_utils.py](MTL_utils.py#L39): trans2tensor stacks stock groups at dim1 yielding [date,stock,feature]。
- [MTL_module.py](MTL_module.py#L128): batch_first=True therefore recurrent sequence is stock axis, not date axis。
- [MTL_module.py](MTL_module.py#L138): random h0/c0 recreated on every forward including prediction。
- [MTL_data_processor.py](MTL_data_processor.py#L92): auxiliary future volatility shift(-21), split has no 21-day purge。
- [MTL_data_processor.py](MTL_data_processor.py#L191): TimeSeriesSplit lacks gap; adjacent train/validation labels overlap future validation prices。
- [MTL_core.py](MTL_core.py#L136): predict_data does not itself call eval; previous validation does call eval, so do not assert always dropout-on。
- [MTL_core.py](MTL_core.py#L145): early stopping updates scalar best loss but never snapshots/restores best weights。
- [MTL_general.py](MTL_general.py#L367): reported strategy returns mean(weights*returns) not sum, costs absent。

源码87仅独立复现历史特征核；源码110是另立计划的因果Ridge扩展，训练标签至少成熟21日，并经原始行情截断重算。三条五年扣费净超额为−8.627%、−24.818%、−22.701%，均不保留。没有将修复后的新研究冒称作者模型复现。
