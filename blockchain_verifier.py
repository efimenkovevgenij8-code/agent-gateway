#!/usr/bin/env python3
"""
blockchain_verifier.py - Zero-Key Automated On-Chain Verification for Replit
Supports:
1. TRON TRC-20 (USDT) via public TronScan API
2. EVM (BSC, Base, Ethereum) via public JSON-RPC (eth_getTransactionReceipt & Transfer logs)
"""
import urllib.request, json, time

TRON_WALLET = "TAiCRVz2HAC59aYYYupkrzBL8C15CT1umR"
EVM_WALLET = "0x95B237733bAfF8208fA06E9d1653681723CbfCa6"

# USDT Contract Addresses
EVM_USDT_CONTRACTS = {
    "bsc": "0x55d398326f99059ff775485246999027b3197955",
    "base": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913", # USDC on Base
    "ethereum": "0xdac17f958d2ee523a2206206994597c13d831ec7"
}

EVM_RPCS = {
    "bsc": ["https://bsc-dataseed.binance.org", "https://binance.llamarpc.com"],
    "base": ["https://mainnet.base.org", "https://base.llamarpc.com"],
    "ethereum": ["https://eth.publicnode.com", "https://ethereum.publicnode.com"]
}

def verify_tron_trc20(tx_hash: str, expected_to: str = TRON_WALLET, min_amount: float = 1.0) -> dict:
    """Verifies a TRON TRC-20 USDT transfer using TronScan public API."""
    tx_hash = tx_hash.strip().lower()
    url = f"https://apilist.tronscanapi.com/api/transaction-info?hash={tx_hash}"
    req = urllib.request.Request(url, headers={"User-Agent": "arena-agent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if not data or "contractRet" not in data:
                return {"valid": False, "reason": "Transaction not found on TronScan yet. Please wait a few seconds."}
            if data.get("contractRet") != "SUCCESS":
                return {"valid": False, "reason": f"Transaction reverted on chain: {data.get('contractRet')}"}
            
            # Check TRC20 transfers
            for tr in data.get("trc20TransferInfo", []):
                to_addr = tr.get("to_address")
                decimals = int(tr.get("decimals", 6))
                amount = float(tr.get("amount_str", 0)) / (10 ** decimals)
                if to_addr == expected_to and amount >= (min_amount - 0.01):
                    return {
                        "valid": True,
                        "network": "TRON TRC-20",
                        "amount_usdt": amount,
                        "sender": tr.get("from_address"),
                        "block": data.get("block")
                    }
            return {"valid": False, "reason": f"No USDT transfer matching target address {expected_to} found in tx."}
    except Exception as e:
        return {"valid": False, "reason": f"Tron verification error: {str(e)}"}

def verify_evm_tx(tx_hash: str, network: str = "bsc", expected_to: str = EVM_WALLET, min_amount: float = 1.0) -> dict:
    """Verifies an EVM token transfer using standard JSON-RPC eth_getTransactionReceipt."""
    tx_hash = tx_hash.strip().lower()
    if not tx_hash.startswith("0x"):
        tx_hash = "0x" + tx_hash
        
    rpc_urls = EVM_RPCS.get(network, EVM_RPCS["bsc"])
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "eth_getTransactionReceipt",
        "params": [tx_hash],
        "id": 1
    }).encode()
    
    for rpc in rpc_urls:
        try:
            req = urllib.request.Request(rpc, data=payload, headers={"Content-Type": "application/json", "User-Agent": "arena-agent/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                res = json.loads(resp.read().decode())
                receipt = res.get("result")
                if not receipt:
                    continue # Try next RPC or not mined yet
                
                status = receipt.get("status")
                if status not in ["0x1", 1, "1"]:
                    return {"valid": False, "reason": "Transaction failed or reverted on chain."}
                
                # Check Transfer event logs (topic 0: 0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef)
                expected_topic_to = "0x000000000000000000000000" + expected_to[2:].lower()
                for log in receipt.get("logs", []):
                    topics = log.get("topics", [])
                    if len(topics) >= 3 and topics[0].lower() == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef":
                        if topics[2].lower() == expected_topic_to:
                            raw_val = int(log.get("data", "0x0"), 16)
                            amount = raw_val / 1e18 if network == "bsc" else raw_val / 1e6
                            if amount >= (min_amount - 0.01):
                                return {
                                    "valid": True,
                                    "network": network.upper(),
                                    "amount_usdt": amount,
                                    "block": int(receipt.get("blockNumber", "0x0"), 16)
                                }
                return {"valid": False, "reason": f"USDT transfer to {expected_to} not detected in event logs."}
        except Exception:
            continue
            
    return {"valid": False, "reason": "Transaction receipt not yet confirmed on public RPC nodes."}

if __name__ == "__main__":
    print("Testing verification module...")
    # Example dry run
    res = verify_tron_trc20("0000000000000000000000000000000000000000000000000000000000000000")
    print("Tron dry run result:", res)
