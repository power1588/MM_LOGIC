import asyncio
import aiohttp
import hmac
import hashlib
import time
import json
from typing import Dict, Any, Optional
from decimal import Decimal

class ExchangeAPI:
    """交易所API接口"""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://testnet.binance.vision" if testnet else "https://api.binance.com"
        self.ws_url = "wss://testnet.binance.vision/ws" if testnet else "wss://stream.binance.com:9443/ws"
        
    async def place_order(self, symbol: str, side: str, type: str, 
                         quantity: str, price: str = None, 
                         timeInForce: str = 'GTC', 
                         newClientOrderId: str = None) -> Dict[str, Any]:
        """下单"""
        params = {
            'symbol': symbol,
            'side': side,
            'type': type,
            'quantity': quantity,
            'timeInForce': timeInForce
        }
        
        if price:
            params['price'] = price
        if newClientOrderId:
            params['newClientOrderId'] = newClientOrderId
            
        return await self._signed_request('POST', '/api/v3/order', params)
        
    async def cancel_order(self, symbol: str, orderId: str = None, 
                          origClientOrderId: str = None) -> Dict[str, Any]:
        """撤单"""
        params = {'symbol': symbol}
        
        if orderId:
            params['orderId'] = orderId
        if origClientOrderId:
            params['origClientOrderId'] = origClientOrderId
            
        return await self._signed_request('DELETE', '/api/v3/order', params)
        
    async def modify_order(self, symbol: str, orderId: str, 
                          new_price: Optional[str] = None,
                          new_quantity: Optional[str] = None) -> Dict[str, Any]:
        """改单 - 通过撤单+重新下单实现"""
        # 获取原订单信息
        order_info = await self.get_order_status(symbol, orderId)
        
        if order_info['status'] not in ['NEW', 'PARTIALLY_FILLED']:
            raise ValueError(f"订单状态不允许改单: {order_info['status']}")
            
        # 撤销原订单
        cancel_result = await self.cancel_order(symbol, orderId)
        
        if cancel_result['status'] != 'CANCELED':
            raise Exception(f"撤销订单失败: {cancel_result}")
            
        # 计算新的数量（考虑已成交部分）
        remaining_qty = float(order_info['origQty']) - float(order_info['executedQty'])
        new_qty = new_quantity if new_quantity else str(remaining_qty)
        
        # 重新下单
        place_params = {
            'symbol': symbol,
            'side': order_info['side'],
            'type': 'LIMIT',
            'quantity': new_qty,
            'timeInForce': 'GTC'
        }
        
        if new_price:
            place_params['price'] = new_price
        else:
            place_params['price'] = order_info['price']
            
        # 使用新的客户端订单ID
        place_params['newClientOrderId'] = f"modify_{orderId}_{int(time.time() * 1000)}"
        
        return await self._signed_request('POST', '/api/v3/order', place_params)
        
    async def get_order_status(self, symbol: str, orderId: str = None,
                              origClientOrderId: str = None) -> Dict[str, Any]:
        """查询订单状态"""
        params = {'symbol': symbol}
        
        if orderId:
            params['orderId'] = orderId
        if origClientOrderId:
            params['origClientOrderId'] = origClientOrderId
            
        return await self._signed_request('GET', '/api/v3/order', params)
        
    async def get_account_info(self) -> Dict[str, Any]:
        """获取账户信息"""
        return await self._signed_request('GET', '/api/v3/account')
        
    async def get_exchange_info(self) -> Dict[str, Any]:
        """获取交易所信息"""
        return await self._public_request('GET', '/api/v3/exchangeInfo')
        
    async def get_ticker_price(self, symbol: str) -> Dict[str, Any]:
        """获取价格信息"""
        params = {'symbol': symbol}
        return await self._public_request('GET', '/api/v3/ticker/price', params)
        
    async def _signed_request(self, method: str, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """签名请求"""
        params['timestamp'] = int(time.time() * 1000)
        params['recvWindow'] = 5000
        
        # 生成签名
        query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        params['signature'] = signature
        
        headers = {
            'X-MBX-APIKEY': self.api_key
        }
        
        return await self._make_request(method, endpoint, params, headers)
        
    async def _public_request(self, method: str, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """公开请求"""
        return await self._make_request(method, endpoint, params or {})
        
    async def _make_request(self, method: str, endpoint: str, params: Dict[str, Any], 
                           headers: Dict[str, str] = None) -> Dict[str, Any]:
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"
        
        async with aiohttp.ClientSession() as session:
            if method == 'GET':
                async with session.get(url, params=params, headers=headers) as response:
                    return await response.json()
            elif method == 'POST':
                async with session.post(url, data=params, headers=headers) as response:
                    return await response.json()
            elif method == 'DELETE':
                async with session.delete(url, params=params, headers=headers) as response:
                    return await response.json()
            else:
                raise ValueError(f"Unsupported HTTP method: {method}") 