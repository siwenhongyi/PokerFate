-- 完成更新后直接热加载而不需要关掉游戏再重启
-- 已经加载的 lua 文件列表
local PACKAGES = {}
for k, _ in pairs(package.loaded) do
	PACKAGES[k] = k
end

-- 重新定义全局变量存储表
-- local GLOBAL_VAR = {}
-- local MT = {__index = GLOBAL_VAR, __newindex = GLOBAL_VAR}
-- setmetatable(_G, MT)

local P = {
	downSize = 0,
	forceUpdate = false,
}
--资源加载检测脚本非游戏初始化环境 模块单独添加
AppLoadRes = P

require "engine.init" 
require "app.Constants"
require "app.VersionConfig"
require "ui.UiManager"
require "ui.init"
require "app.config"
require "manager.LanguageManager"
LanguageManager:init()

local HOT_VERSION = "1.0.0"

function P:checkVersion(isWhite)
	self:_loadVersionInfo(isWhite, function (data) --http get 对比服务端json配置
		print("[AppLoadRes] checkVersion", json.encode(data))
		if bee.isAndroid then
			if G_CHNL_ID == 5 then
				self:checkDownload(data.android)
			else
				self:checkDownload(data.android_official)
			end
		elseif bee.isIos then
			self:checkDownload(data.ios)
		else
			self:checkDownload(data.windows)
		end
	end, function()
		self:onUpdateFinish(false, "check_error")
		bee.logEvent("net_lose_version", UrlManager:getServerUrl())
	end)
end

function P:_loadVersionInfo(isWhite, cb, failCb)
	if bee.isDev then
		local path = CS.FileUtils.GetWritePath() .. HOT_VERSION .. (isWhite and "_version_beta.json" or "_version.json")
		local s = CS.FileUtils.ReadAllBytesSafely(path)
		if s and "" ~= s then
			local data = json.decode(s)
			if data then
				cb(data)
				return
			end
		end
	end
	local jsonUrl = self:getRemoteUrl() .. HOT_VERSION .. (isWhite and "_version_beta.json" or "_version.json") .. "?t=" .. os.time()
	Net:getUrl(jsonUrl, cb, failCb)
end

function P:checkDownload(data, force)
	self._checkData = data
	if not data then
		self:onUpdateFinish(false)
		return false
	end
	if self:compareVer(G_REMOTE_VERSION, data.res) < 0 then
		G_REMOTE_VERSION = data.res
	end
	local fullVer = G_APP_VERSION
	print("[AppLoadRes] checkDownload", json.encode(data), fullVer, data.ver)
	local c1 = self:compareVer(fullVer, data.ver)
	if -1 == c1 then
		if self._isSlient and not force then
			LocalStore:saveTableData("addr_app_version_info", data)
		else
			if data.min_ver then
				local c2 = self:compareVer(fullVer, data.min_ver)
				if -1 == c2 then
					self:showAppDownload(true)
					return true
				else
					self:showAppDownload(false)
					return true
				end
			else
				self:showAppDownload(true)
				return true
			end
		end
		return true
	end
	if not force then
		self:checkResDownload(data)
	end
	return false
end

local function print_func_ref_by_csharp()
    local registry = debug.getregistry()
    for k, v in pairs(registry) do
        if type(k) == 'number' and type(v) == 'function' and registry[v] == k then
            local info = debug.getinfo(v)
            print(string.format('%s:%d', info.short_src, info.linedefined))
        end
    end
end

local function onComplete(status)
	if "none" == status then
		P:onUpdateFinish(false)
	elseif "complete" == status then
		P:onUpdateFinish(true)
	else
		P:onUpdateFinish(false, status)
	end
end
local function onProgress(progress)
	if not P._isSlient then
		bee.emit("evt_remote_res_progress", progress)
	end
end

function P:checkResDownload(data)
	if 0 <= self:compareVer(G_UPDATE_VERSION, data.res) then
		self:onUpdateFinish(false)
		return
	end
	
	self._downloadUrl = data.url .. "/" .. data.res
	local url = self:getRemoteUrl() .. self._downloadUrl
	if not self._isSlient then
		CS.AppLoader.Instance:DoDownLoad(url, onComplete, onProgress, function(size)
        	bee.logEvent("login-update")
			self.downSize = size
			self.forceUpdate = false
			local button = 2
			if -1 == self:compareVer(G_UPDATE_VERSION, data.min_res) then	-- 要强制更新
				button = 1
				self.forceUpdate = true
			end
			local params =
			{
				button = button,
				title = _T("LAB_UPDATE_TITILE_1"),
				text = _F("LAB_UPDATE_TIPS_2", "<color=#EC0B7A>" .. tostring(self:getMB(size)) .. "</color> MB"),
				surStr = _T("LAB_UPDATE_BTN_3"),
				cancelStr = _T("LAB_UPDATE_BTN_1"),
				noClose = button == 1,
				onSure = function()
					if bee.isInHome() then
						G_DOWNLOAD_REMOTE = true
						bee.enterScene("StartScene")
						return
					end
					self:startDownload()
        			bee.logEvent("login-update-immediately")
					CS.SdkHelper.setScreenSleep(false)
				end,
				onCancel = function()
					self:onUpdateFinish(false)
        			bee.logEvent("login-update-cancel")
				end
			}
			
			if G_CHECK_FORCE_UPDATE then
				G_CHECK_FORCE_UPDATE = nil
				if not self.forceUpdate then
					if G_CHECK_FORCE_UPDATE_NEEDREDDOT then
						G_CHECK_FORCE_UPDATE_NEEDREDDOT = nil
						RedManager:addTagWithNum(1, RedTag.UpdateTag)
					end
					bee.emit("evt_refreshUpdateInfo")
					return
				end
				params.inPop = true
			end
			UiManager:showUI("UpdateVersion", params)
		end)
	else
		CS.AppLoader.Instance:DoSlientDownload(url, onComplete, onProgress)
	end
end

function P:startDownload()
	if self._downloadUrl and bee.checkVersion("1.2.9") then
		self:nextRemoteUrl()
		CS.AppLoader.SetHost(self:getRemoteUrl() .. self._downloadUrl)
	end
	CS.AppLoader.Instance:StartDownload(onComplete, onProgress)
end

-- isFail 是否更新失败
function P:onUpdateFinish(isUpdate, isFail)
	print("===== gggggggggg onUpdateFinish", isUpdate, isFail)
	if self._isSlient then
		if isUpdate then
			bee.needReloadGame = true
		end
		return
	end
	if isUpdate then
        bee.logEvent("login-update-success")
		CS.AppLoader.ExecuteSlient(false)
		-- print_func_ref_by_csharp()
		bee.enterScene("StartScene")
		-- self:unLoadPakage()
	else
		require("app.init")
		bee.emit("evt_updateFinish")
		if isFail then
			bee.logEvent("login-update-failure")
			self:nextRemoteUrl()
		end
		if isFail and self._failCb then
			self._failCb(isFail)
		elseif self._updateCb then
			self._updateCb()
		end
		
		-- bee.emit("evt_loadDefautlAssetsDone")
	end
end

function P:showAppDownload(isForce)
	local params =
	{
		button = isForce and 1 or 2,
		title = _T("LAB_UPDATE_TITILE_1"),
		text = _T("LAB_UPDATE_TIPS_1"),
		sureStr = _T("LAB_UPDATE_BTN_2"),
		cancelStr = _T("LAB_UPDATE_BTN_1"),
		noClose = isForce,
		onSure = function()
			CU.Application.OpenURL(G_QGLK)
			Game:quit()
			return true
		end,
		onCancel = function()
			self:checkResDownload(self._checkData)
			if self._isSlient then
				require("app.init")
				bee.emit("evt_updateFinish")
				if self._updateCb then
					self._updateCb()
				end
			end
		end
	}
	
	UiManager:showUI("UpdateVersion", params)
end

function P:unLoadPakage()
	--if PACKAGES then
		print("[AppLoadRes] unLoadPakage")
		--UiManager:releaseResHandles()
		ObjectCache:clearAll()
		SpriteManager:RemoveAll()
		ResManager:ReleaseHandles()
		ResManager:UnloadUnusedAssets()
		-- setmetatable(_G, nil)
		for k, _ in pairs(package.loaded) do
			-- if nil == PACKAGES[k] then
				package.loaded[k] = nil
			-- end
		end
		package.loaded["main"] = nil
		package.loaded["appload.AppLoadRes"] = nil
		PACKAGES = nil
		-- GLOBAL_VAR = nil
		MT = nil
	--end
end

function P:compareVer(ver1,ver2)
	local ver1s= string.split(ver1,".")
	local ver2s= string.split(ver2,".")
	for k, v in ipairs(ver1s) do
		if tonumber(v) < tonumber(ver2s[k]) then
			return -1
		elseif tonumber(v) > tonumber(ver2s[k])  then
			return 1
		end
	end
	return 0
end

function P:getMB(size)
	return math.floor(size / (1024 * 1024) * 100) / 100
end

function P:checkUpdate(isSlient, isWhite, cb, failCb)
	print("[AppLoadRes] checkUpdate", CS.AppLoader.isReload, isSlient)
	self._isSlient = isSlient
	self._updateCb = cb
	self._failCb = failCb
	-- if CS.AppLoader.isReload then
	-- 	if cb then cb() end
	-- 	self._updateCb = nil
	-- 	return false
	-- end
	if self._isSlient then
		local data = LocalStore:getTableData("addr_app_version_info")
		if data then
			if self:checkDownload(data, true) then
				return true
			end
			LocalStore:deleteValueForKey("addr_app_version_info")
		end
	end
	self:checkVersion(isWhite)
	if self._isSlient then
		return false
	end
	return true;
end

function P:executeSlient()
	if bee.needReloadGame then
		bee.needReloadGame = nil
		CS.AppLoader.isReload = true
		CS.AppLoader.ExecuteSlient(false)
		bee.enterScene("StartScene")
		return true
	end
	return false
end

-- 检查下载分包 index: 子包序号，从1开始
function P:checkPackage(index)
	if G_IGNORE_PACK then return true end
	
	index = index or 1
	require("tpl.tpl_sub_config")
	print("AppLoadRes checkPackage", index)
	for k, v in ipairs(tpl_sub_config_list) do
		if k == index then
			if PlayerModel and PlayerModel:getCurLevel() >= v.level then
				self:_tryDownloadPackage(k)
				break
			else
				self:checkPackage(index + 1)
				break
			end
		end
	end
end

function P:_tryDownloadPackage(index)
	if self["_isCheckPackage" .. index] then
		self:checkPackage(index + 1)
		return
	end
	self["_isCheckPackage" .. index] = true

	local d = tpl_sub_config_list[index]
	if not d then
		return
	end

	local ver = LocalStore:getStringForKey("app_sub_package_version_" .. d.id, "")
	if ver ~= bee.subinfo[d.id] then
		print("[AppLoadRes] checkPackage")
		
		local url = "Android"
		if bee.isAndroid then
			if G_CHNL_ID == 5 then
				url = "Android"
			else
				url = "Android_official"
			end
		elseif bee.isIos then
			url = "iOS"
		else
			url = "StandaloneWindows64"
		end
		CS.AppLoader.Instance:DoDownloadSubPackage(self:getRemoteUrl() .. url .. "/" .. G_APP_VERSION .. "_sub", d.id, function(status)
			if "none" == status then
				self["_isCheckPackage" .. index] = nil
			else
				if not bee.subinfo then return end
				LocalStore:setStringForKey("app_sub_package_version_" .. d.id, bee.subinfo[d.id])
				self:checkPackage(index + 1)
				bee.emit("evt_sub_package_sucess", d.id)
			end
		end, function(progress)
			bee.emit("evt_sub_remote_res_progress", progress)
		end)
	else
		self:checkPackage(index + 1)
	end
end

-- 检查子包的资源
function P:checkSubinfo()
	if G_IGNORE_PACK then return end
	bee.subinfo = {}
	local info = CS.FileUtils.ReadBytesFromRes("subinfo")
	if info and "" ~= info then
		local ms = string.split(info, "\n")
		for _, v in ipairs(ms) do
			local i = string.split(v, ",")
			bee.subinfo[tonumber(i[1])] = i[2]
		end
	end
	print("AppLoadRes subinfo ", info)
	if tpl_sub_config then
		local key = ""
		for _, v in ipairs(tpl_sub_config_list) do
			if not bee.subinfo[v.id] then
				bee.subinfo[v.id] = G_APP_VERSION
			end
			key = "app_sub_package_version_" .. v.id
			if LocalStore:getStringForKey(key, "") ~= bee.subinfo[v.id] then
				LocalStore:setStringForKey(key, "")
			end
		end
	end
end

function P:nextRemoteUrl()
    self._remoteIndex = (self._remoteIndex or 0) + 1
    if self._remoteIndex > 3 then
        self._remoteIndex = 1
    end
    LocalStore:setIntegerForKey("remote_host_index", self._remoteIndex)
end

function P:getRemoteUrl()
	if not self._remoteIndex then
		self._remoteIndex = LocalStore:getIntegerForKey("remote_host_index", 1)
	end
	
    if self._remoteIndex and _G["G_REMOTE_RES_HOST_" .. self._remoteIndex] then
        return _G["G_REMOTE_RES_HOST_" .. self._remoteIndex]
    end
    if self._remoteIndex ~= 1 then
        self._remoteIndex = 1
        LocalStore:setIntegerForKey("remote_host_index", self._remoteIndex)
    end
    return G_REMOTE_RES_HOST
end

P:checkSubinfo()

-- 检查子包是否已经下载 pack: 子包序号，从1开始
bee.checkPackage = function(pack)
	if G_IGNORE_PACK then return true end
    if bee.isEditor then
        if CS.AppLoader.playMode <= 0 then
            return true
        end
    end
    if not pack or pack < 1 then return true end
    return LocalStore:getStringForKey("app_sub_package_version_" .. pack) == bee.subinfo[pack]
end

return P

