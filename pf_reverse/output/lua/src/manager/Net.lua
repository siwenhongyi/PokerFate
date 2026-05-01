local pb = require "pb"
WebSocket   = CS.WebSocketManager.Instance
-- 网络连接管理器
local P = {
    _cbs = {},
	recver = nil,	-- 本地模拟服务器

    connectCb = nil,
    closeCb = nil,
    errorCb = nil,

	_reqList = {},	-- 队列延迟发送列表
	_sendMap = {},	-- 已发送的请求时间 name: time
	_delays = {},	-- 最近发送的请求响应延迟
	_httpdelays = {},	-- http 的延迟
}
Net = P

local PACK_HEAD_LEN = 4

local function getNtohs(szBigEndian)
	local nTotal = 0
	for i = 1, string.len(szBigEndian) do
		local char = string.sub(szBigEndian, i, i)
		local number = string.byte(char)
		local nBit = 8 * (string.len(szBigEndian) - i)
		nTotal = nTotal + number * math.pow(2, nBit)
	end
	return nTotal
end

local function getHtons(nInt, nDigit)
	local szBigEndian = ''
	for i = 1, nDigit do
		local nBit = 8 * (nDigit - i)
		local nPow = math.pow(2, nBit)
		local number = math.floor(nInt / nPow)
		nInt = nInt - number * nPow
		szBigEndian = szBigEndian..string.char(number)
	end
	return szBigEndian
end

local function packNetData(szPackType, msg)
	local szPbData = pb.encode(szPackType, msg)
	local nPackLen = 2 + string.len(szPackType) + string.len(szPbData) + 4
	local strSend = getHtons(nPackLen, 4)..getHtons(string.len(szPackType), 2)
	local roomId = 0
	if GameModel.data then
		roomId = GameModel.data:getRoomId()
	end
	strSend = strSend..szPackType..getHtons(roomId, 4)..szPbData
	return strSend
end

WebSocket:SetConnectCb(function(ret)
	Net._connecting = nil
    if Net.connectCb then
        Net.connectCb(ret)
		Net.connectCb = nil
    end
end)

WebSocket:SetRecvCb(function(body)
	if Net._waitNet then
		Net._waitNet = nil
		UiManager:hideLoadingMask("WaitNet")
	end
	local szDataCache = body
	if string.len(szDataCache) < PACK_HEAD_LEN then
		print('不夠包頭長度')
		return
	end

	local nPackLen = getNtohs(string.sub(szDataCache, 1, PACK_HEAD_LEN))
	if string.len(szDataCache) - 4 < nPackLen then--还没有接受完
		return
	end
	local nPackTypeLen = getNtohs(string.sub(szDataCache, 5, 6))

	local szPackType = string.sub(szDataCache, 6 + 1, 6 + nPackTypeLen)
	local roomId = getNtohs(string.sub(szDataCache, 6 + nPackTypeLen + 1, 10 + nPackTypeLen))
	local szPackBody = string.sub(szDataCache, 10 + nPackTypeLen + 1, nPackLen + 4)
	local pbname = string.sub(szPackType, 1, -4)

	if not GameModel:isStopGameMsg(szPackType) then
		local msg = pb.decode(szPackType, szPackBody)
		if msg then
			bee.protoDefault(szPackType, msg)
			if not bee.isRelease and "pb.HeartBeatRSP" ~= szPackType and "pb.HBPingRSP" ~= szPackType then
				print("[Net] onRecv", scheduler.timeSpend, szPackType, json.encode(msg))
			else
			end

			local name = string.sub(szPackType, 4)
			if net[name] then
				net[name](net, msg)
			end

			if not msg.code or 0 == msg.code then
				bee.emit("evt_" .. name, msg)
			end
			Net:onErrorCode(msg)

			name = string.sub(name, 1, #name - 3)
			if Net._sendMap[name] then
				local delay = scheduler.timeSpend - Net._sendMap[name]
				if delay < 3 then
					table.insert(Net._delays, delay)
				end
				Net._sendMap[name] = nil
				if #Net._delays > 10 then
					table.remove(Net._delays, 1)
				end
			end
			
			if Net._cbs[name] and string.sub(szPackType, #szPackType - 2) == "RSP" then
				local cb = Net._cbs[name]
				Net._cbs[name] = nil
				cb(msg)
			end
		end
	end

	-- --获取剩下的数据--
	-- local szNextPack = string.sub(szDataCache, nPackLen + 5, string.len(szDataCache))
	-- self._recvDataCache = {}
	-- if szNextPack and szNextPack ~= "" then
	-- 	table.insert(self._recvDataCache, szNextPack)
	-- end

	-- if G.tbProtocols[szPackType] then
	-- 	G.loadingMgr.getInstance():removeLoadingLayer(szPackType)
	-- 	G.tbProtocols[szPackType].callFunc(szPackType, szPackBody)
	-- end

	-- --检查包里是否还有数据
	-- if #self._recvDataCache > 0 then
	-- 	self:onRecvData()
	-- end
end)

WebSocket:SetCloseCb(function()
	print("WebSocket:SetCloseCb++++++")
	Net._connecting = nil
    if Net.closeCb then
        Net.closeCb()
    end
	-- if PlayerModel then
	-- 	PlayerModel:setIsLogin(false)
	-- end
	-- if #Net._reqList > 0 then
	-- 	Net._reqList = {}
	-- end
	Net._cbs = {}
	bee.emit("evt_netClosed")
end)

WebSocket:SetErrorCb(function(code, msg)
	print("WebSocket:SetErrorCb++++++", code)
	bee.logEvent("net_lose", UrlManager:getServerUrl(), code)
	if Net._connecting then
		UrlManager:nextServerUrl()
		Net._connecting = nil
		if Net.connectCb then
			Net.connectCb(false)
			Net.connectCb = nil
		end
	end
    if Net.errorCb then
        Net.errorCb(code, msg)
    end
	-- if PlayerModel then
	-- 	PlayerModel:setIsLogin(false)
	-- end
	-- if #Net._reqList > 0 then
	-- 	Net._reqList = {}
	-- end
	bee.once(-1, function()
		bee.emit("evt_netClosed")
	end)
	Net._cbs = {}
end)

function P:connect(url, cb)
	self._connecting = true
    self.connectCb = cb
    WebSocket:ConnectedToServer(url)
	self._sendMap = {}
	self._delays = {}
end

function P:isConnected()
    return WebSocket:IsConnected()
end

function P:closeSocket()
	self._cbs = {}
    WebSocket:CloseSocket()
end

function P:onErrorCode(msg)
	if msg.code and msg.code ~= 0 then
		local e = tpl_errorCode[msg.code]
		if e and e.tip ~= 0 then
			if e.id == "ERR_MAINTAIN_SOON_FORBID_GAME" then
				local ui = UiManager:showUI("UpdateShutdown", {
					title = _T("LAB_UPDATE_TITILE_2"),
					text = _T("LAB_UPDATE_INFO_3"),
					button = 1,
					noClose = true,
					onSure = function()
					end,
				})
			elseif e.id == "HTTP_SERVER_STOP" then
				UiManager:showTip({
					title = _T("LAB_UPDATE_TITILE_3"),
					text = _T("LAB_UPDATE_INFO_4"),
					button = 1,
				})
			elseif e.id == "HTTP_IP_BLOCKED" or e.id == "HTTP_IMEI_BLOCKED" or e.id == "HTTP_ACCOUNT_BLOCKED" then
				UiManager:showUI("LoginBanTipDialog", {
					msg = msg,
					err = e,
				})
			else
				UiManager:showError(_T(e.id))
			end
		end
	end
end

function P:getDelay()
	local dt = 0
	for _, v in ipairs(self._delays) do
		dt = dt + v
	end
	if dt > 0 then
		return dt / #self._delays
	end
	return dt
end

function P:getHttpDelay()
	local dt = 0
	for _, v in ipairs(self._httpdelays) do
		dt = dt + v
	end
	if dt > 0 then
		return dt / #self._httpdelays
	end
	self._httpdelays = {}
	return dt
end

function P:setRecver(recver)
	self.recver = recver
end

function P:sendReq(name, req, cb)
	if not bee.isRelease and name ~= "pb.HeartBeatREQ" then
    	print("[Net] send", scheduler.timeSpend, name, json.encode(req))
	end
	if self.recver and self.recver:onRecv(name, req) then
		return
	end
	local reqName = string.sub(name, 4, #name - 3)
	if cb then
		self._cbs[reqName] = cb
	end
	local strSend = packNetData(name, req)
	WebSocket:Send(strSend)
	self._sendMap[reqName] = scheduler.timeSpend
end

function P:get(url, onSuc, onFail, noTipError, immediately)
	if not immediately and not bee.checkCd(url, 0.5) then
		return
	end
	if bee.isDev or bee.isEditor then
		print("[Net] get " .. UrlManager:getHttpUrl() .. url)
	end
	local dt = scheduler.timeSpend
	CS.HttpManager.Instance:get(UrlManager:getHttpUrl() .. url,function (jsonStr)
		if bee.isDev or bee.isEditor then
			print("[Net] get onSuc", url .. " " .. jsonStr)
		end
		local d = json.decode(jsonStr)
		if onSuc then
			onSuc(d)
			if not noTipError then
				self:onErrorCode(d)
			end
		end
		table.insert(self._httpdelays, scheduler.timeSpend - dt)
	end, function()
		UrlManager:nextHttpUrl()
		if onFail then
			onFail()
		end
	end, 10, self:getHttpHeader())
end

function P:getUrl(url, onSuc, onFail, noTipError)
	-- if not bee.checkCd(url, 0.5) then
	-- 	return
	-- end
	if bee.isDev or bee.isEditor then
		print("[Net] get " .. url)
	end
	local dt = scheduler.timeSpend
	CS.HttpManager.Instance:get(url,function (jsonStr)
		if bee.isDev or bee.isEditor then
			print("[Net] get onSuc",jsonStr)
		end
		local d = json.decode(jsonStr)
		if onSuc then
			onSuc(d)
			if not noTipError then
				self:onErrorCode(d)
			end
		end
		table.insert(self._httpdelays, scheduler.timeSpend - dt)
	end,onFail,10,self:getHttpHeader())
end

function P:post(url, req, onSuc, onFail, noTipError)
	if (not req or not req.immediately) and not bee.checkCd(url, 0.5) then
		return
	end
	local reportStr = json.encode(self:addSaltArgs(req))
	reportStr = string.gsub(reportStr, "\\'", "'")
	if bee.isDev or bee.isEditor then
		print("[Net] post " .. UrlManager:getHttpUrl() .. url .. " " .. reportStr .. " " .. (PlayerModel and PlayerModel:getAuthorization() or ""))
	end
	local mask = req and req.mask
	if mask then
		UiManager:showLoadingMask(mask)
	end
	local dt = scheduler.timeSpend
	CS.HttpManager.Instance:post(UrlManager:getHttpUrl() .. url,reportStr,function (jsonStr)
		if mask then
			UiManager:hideLoadingMask(mask)
		end
		if bee.isDev or bee.isEditor then
			print("[Net] post onSuc", url .. " " .. jsonStr)
		end
		local d = json.decode(jsonStr)
		if onSuc then
			-- onSuc(d and d.tars_ret or nil)
			onSuc(d)
			if not noTipError or d.code == -52 or d.code == -53 or d.code == -54 then
				self:onErrorCode(d)
			end
		end
		table.insert(self._httpdelays, scheduler.timeSpend - dt)
	end, function()
		if mask then
			UiManager:hideLoadingMask(mask)
		end
		UrlManager:nextHttpUrl()
		if onFail then
			onFail()
		end
	end, 10, self:getHttpHeader())
end

function P:postUrl(url, req, onSuc, onFail, noTipError)
	-- if not bee.checkCd(url, 0.5) then
	-- 	return
	-- end
	local reportStr = json.encode(req)
	reportStr = string.gsub(reportStr, "\\'", "'")
	if bee.isDev or bee.isEditor then
		print("[Net] post " .. url .. " " .. reportStr)
	end
	local dt = scheduler.timeSpend
	CS.HttpManager.Instance:post(url,reportStr,function (jsonStr)
		if bee.isDev or bee.isEditor then
			print("[Net] post onSuc",jsonStr)
		end
		local d = json.decode(jsonStr)
		if onSuc then
			-- onSuc(d and d.tars_ret or nil)
			onSuc(d)
			if not noTipError then
				self:onErrorCode(d)
			end
		end
		table.insert(self._httpdelays, scheduler.timeSpend - dt)
	end, onFail, 10, self:getHttpHeader())
end

function P:addSaltArgs(args)
	args = args or {}
    local signs = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    local s = ""
    for i = 1, 6 do
        local idx = math.random(1, #signs)
        s = s .. string.sub(signs, idx, idx)
    end
    args.random = s
    if not args.ts then
        args.ts = tostring(os.time())
    end
    args.sign = CS.Utils.GetMd5("random=" .. args.random .. "&ts=" .. tostring(args.ts) .. "&salt=" .. SALT)
    if not args.chnl then
        args.chnl = G_CHNL_ID
    end
    return args
end

function P:uploadFile(url, path, onSuc, onFail)
	if not string.find(url, "http") then
		url = UrlManager:getHttpUrl() .. url
	end
	CS.HttpManager.Instance:downLoadFile(url, path, onSuc, onFail, -1, self:getHttpHeader())
end

function P:downloadFile(url, path, onSuc, onFail)
	if not string.find(url, "http") then
		url = UrlManager:getHttpUrl() .. url
	end
	CS.HttpManager.Instance:downLoadFile(url, path, onSuc, onFail, -1, self:getHttpHeader())
end

function P:getHttpHeader()
	return table.concat({
		"Content-Type: application/json; charset=utf-8",
		"Version: " .. G_UPDATE_VERSION,
		"Authorization: " .. (PlayerModel and PlayerModel:getAuthorization() or ""),
	}, "\n")
end

function P:showWaitNet()
	self._waitNet = true
	UiManager:showLoadingMask("WaitNet")
end

return P