#!/usr/bin/env python3
"""
调试孤儿持仓平仓逻辑
"""

def test_orphaned_positions_logic():
    """测试孤儿持仓平仓逻辑"""
    print("🧪 测试孤儿持仓平仓逻辑")
    print("=" * 50)
    
    # 模拟策略状态
    status = {
        'BTC/USDT:USDT': 1,    # 策略选中的多头
        'ETH/USDT:USDT': -1,   # 策略选中的空头
        'SOL/USDT:USDT': 0,    # 策略未选中
        'ADA/USDT:USDT': 0,    # 策略未选中
    }
    
    print("📋 当前策略状态:")
    for pair, status_val in status.items():
        if status_val == 1:
            print(f"   ✅ {pair}: 多头 (status: {status_val})")
        elif status_val == -1:
            print(f"   ✅ {pair}: 空头 (status: {status_val})")
        else:
            print(f"   ❌ {pair}: 未选中 (status: {status_val})")
    
    # 模拟持仓数据
    all_positions = {
        'BTC/USDT:USDT': {
            'symbol': 'BTC/USDT:USDT',
            'side': 'long',
            'contracts': 0.1,
            'value': 4000,
            'price': 40000
        },
        'ETH/USDT:USDT': {
            'symbol': 'ETH/USDT:USDT',
            'side': 'short',
            'contracts': 1.0,
            'value': 3000,
            'price': 3000
        },
        'SOL/USDT:USDT': {
            'symbol': 'SOL/USDT:USDT',
            'side': 'long',
            'contracts': 10.0,
            'value': 1000,
            'price': 100
        },
        'ADA/USDT:USDT': {
            'symbol': 'ADA/USDT:USDT',
            'side': 'short',
            'contracts': 1000.0,
            'value': 500,
            'price': 0.5
        }
    }
    
    print(f"\n📊 模拟持仓数据:")
    for symbol, pos_info in all_positions.items():
        print(f"   - {symbol}: {pos_info['side']} {pos_info['contracts']} contracts")
    
    # 获取策略选中的币种
    print(f"\n📋 Step 1: 获取当前策略选中的币种...")
    selected_positions = set()
    for pair, status_val in status.items():
        if status_val == 1 or status_val == -1:
            selected_positions.add(pair)
            print(f"   ✅ 策略选中: {pair} (status: {status_val})")
    
    print(f"   策略选中 {len(selected_positions)} 个币种")
    
    # 查找需要平仓的持仓
    print(f"\n🔍 Step 2: 查找需要平仓的持仓...")
    orphaned_positions = {}
    for symbol, pos_info in all_positions.items():
        if symbol not in selected_positions:
            orphaned_positions[symbol] = pos_info
            print(f"   🚨 需要平仓: {symbol} - {pos_info['side']} {pos_info['contracts']} contracts (不在当前策略选中范围内)")
        else:
            print(f"   ✅ 保留持仓: {symbol} - {pos_info['side']} {pos_info['contracts']} contracts (在当前策略选中范围内)")
    
    print(f"\n📊 Step 3: 平仓统计...")
    print(f"   总持仓数: {len(all_positions)}")
    print(f"   策略选中持仓数: {len(all_positions) - len(orphaned_positions)}")
    print(f"   需要平仓数: {len(orphaned_positions)}")
    
    if not orphaned_positions:
        print("   ✅ 没有需要平仓的持仓")
        return
    
    # 模拟平仓操作
    print(f"\n🔄 Step 4: 模拟平仓操作...")
    closed_count = 0
    
    for symbol, pos_info in orphaned_positions.items():
        print(f"\n   📝 正在平仓: {symbol} - {pos_info['side']} {pos_info['contracts']} contracts")
        
        # 模拟平仓
        if pos_info['side'] == 'long':
            print(f"   📤 平仓多头: 卖出 {pos_info['contracts']} 张")
            print(f"   ✅ 模拟成功平仓: {symbol}")
        elif pos_info['side'] == 'short':
            print(f"   📤 平仓空头: 买入 {pos_info['contracts']} 张")
            print(f"   ✅ 模拟成功平仓: {symbol}")
        
        closed_count += 1
    
    print(f"\n📊 Step 5: 平仓结果统计...")
    print(f"   成功平仓: {closed_count} 个")
    print(f"   总计处理: {len(orphaned_positions)} 个持仓")
    
    print(f"\n✅ 测试完成!")
    print(f"\n💡 总结:")
    print(f"   - 策略选中的币种: {list(selected_positions)}")
    print(f"   - 需要平仓的币种: {list(orphaned_positions.keys())}")
    print(f"   - 保留的币种: {[s for s in all_positions.keys() if s not in orphaned_positions]}")

if __name__ == "__main__":
    test_orphaned_positions_logic() 