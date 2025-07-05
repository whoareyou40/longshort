#!/usr/bin/env python3
"""
网络连接诊断脚本
检查OKX API连接、网络连通性和配置状态
"""

import asyncio
import ccxt
import requests
import socket
import time
from datetime import datetime
from okx_config import OKXConfig

def check_basic_network():
    """检查基本网络连接"""
    print("🌐 检查基本网络连接...")
    
    # 测试DNS解析
    try:
        ip = socket.gethostbyname('www.okx.com')
        print(f"   ✅ DNS解析正常: www.okx.com -> {ip}")
    except socket.gaierror as e:
        print(f"   ❌ DNS解析失败: {e}")
        return False
    
    # 测试HTTP连接
    try:
        response = requests.get('https://www.okx.com', timeout=10)
        print(f"   ✅ HTTP连接正常: 状态码 {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"   ❌ HTTP连接失败: {e}")
        return False
    
    # 测试OKX API连接
    try:
        response = requests.get('https://www.okx.com/api/v5/public/time', timeout=10)
        if response.status_code == 200:
            print(f"   ✅ OKX API连接正常: {response.json()}")
        else:
            print(f"   ⚠️ OKX API响应异常: 状态码 {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"   ❌ OKX API连接失败: {e}")
        return False
    
    return True

def check_config():
    """检查配置状态"""
    print("\n⚙️ 检查配置状态...")
    
    config = OKXConfig()
    
    # 检查API密钥
    if config.API_KEY:
        print(f"   ✅ API_KEY已配置: {config.API_KEY[:8]}...")
    else:
        print("   ❌ API_KEY未配置")
        return False
    
    if config.SECRET_KEY:
        print(f"   ✅ SECRET_KEY已配置: {config.SECRET_KEY[:8]}...")
    else:
        print("   ❌ SECRET_KEY未配置")
        return False
    
    if config.PASSPHRASE:
        print(f"   ✅ PASSPHRASE已配置: {config.PASSPHRASE[:8]}...")
    else:
        print("   ❌ PASSPHRASE未配置")
        return False
    
    print(f"   📊 沙盒模式: {'是' if config.SANDBOX else '否'}")
    print(f"   📊 交易对数量: {len(config.TRADING_PAIRS)}")
    
    return True

async def test_okx_connection():
    """测试OKX CCXT连接"""
    print("\n🔗 测试OKX CCXT连接...")
    
    config = OKXConfig()
    
    try:
        # 创建exchange对象
        exchange = ccxt.okx({
            'apiKey': config.API_KEY,
            'secret': config.SECRET_KEY,
            'password': config.PASSPHRASE,
            'sandbox': config.SANDBOX,
            'enableRateLimit': True,
        })
        
        print("   📡 正在连接OKX...")
        
        # 测试加载市场数据
        markets = exchange.load_markets()
        print(f"   ✅ 市场数据加载成功: {len(markets)} 个市场")
        
        # 测试获取服务器时间
        server_time = exchange.fetch_time()
        local_time = int(time.time() * 1000)
        time_diff = abs(server_time - local_time)
        print(f"   ✅ 服务器时间同步: 差异 {time_diff}ms")
        
        # 测试获取账户余额
        try:
            balance = exchange.fetch_balance()
            print(f"   ✅ 账户余额获取成功: {len(balance['total'])} 个币种")
        except Exception as e:
            print(f"   ⚠️ 账户余额获取失败: {e}")
        
        # 测试获取持仓
        try:
            positions = exchange.fetch_positions(params={'instType': 'SWAP'})
            print(f"   ✅ 持仓数据获取成功: {len(positions)} 个持仓")
        except Exception as e:
            print(f"   ⚠️ 持仓数据获取失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ OKX连接失败: {e}")
        return False

async def test_trading_pairs():
    """测试交易对可用性"""
    print("\n📊 测试交易对可用性...")
    
    config = OKXConfig()
    
    try:
        exchange = ccxt.okx({
            'apiKey': config.API_KEY,
            'secret': config.SECRET_KEY,
            'password': config.PASSPHRASE,
            'sandbox': config.SANDBOX,
            'enableRateLimit': True,
        })
        
        markets = exchange.load_markets()
        
        available_count = 0
        unavailable_count = 0
        
        for pair in list(config.TRADING_PAIRS)[:10]:  # 只测试前10个
            if pair in markets:
                try:
                    ticker = exchange.fetch_ticker(pair)
                    print(f"   ✅ {pair}: 价格 {ticker['last']}")
                    available_count += 1
                except Exception as e:
                    print(f"   ❌ {pair}: 获取价格失败 - {e}")
                    unavailable_count += 1
            else:
                print(f"   ❌ {pair}: 市场不存在")
                unavailable_count += 1
        
        print(f"   📊 可用: {available_count}, 不可用: {unavailable_count}")
        
    except Exception as e:
        print(f"   ❌ 测试交易对失败: {e}")

async def main():
    """主诊断函数"""
    print("🔍 OKX连接诊断工具")
    print("=" * 50)
    print(f"开始时间: {datetime.now()}")
    
    # 基本网络检查
    network_ok = check_basic_network()
    
    # 配置检查
    config_ok = check_config()
    
    if not network_ok:
        print("\n❌ 基本网络连接失败，请检查网络设置")
        return
    
    if not config_ok:
        print("\n❌ 配置检查失败，请检查API密钥配置")
        return
    
    # OKX连接测试
    okx_ok = await test_okx_connection()
    
    # 交易对测试
    await test_trading_pairs()
    
    print("\n" + "=" * 50)
    print("诊断结果总结:")
    print(f"   基本网络: {'✅ 正常' if network_ok else '❌ 异常'}")
    print(f"   配置状态: {'✅ 正常' if config_ok else '❌ 异常'}")
    print(f"   OKX连接: {'✅ 正常' if okx_ok else '❌ 异常'}")
    
    if network_ok and config_ok and okx_ok:
        print("\n🎉 所有检查通过，连接正常！")
    else:
        print("\n⚠️ 发现问题，请根据上述信息进行排查")

if __name__ == "__main__":
    asyncio.run(main()) 