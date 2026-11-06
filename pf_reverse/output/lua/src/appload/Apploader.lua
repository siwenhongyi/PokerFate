-- AppLoader.lua
-- 参考 AppLoader.cs 实现，用于检查远程资源并下载
-- 提供与 C# AppLoader 相同的 API 接口

local P = {
	-- 常量定义
	fileListName = "0filelist.txt",
	fileListNameSub = "0filelist{1}.txt",
	catalogName = "catalog_1.0.0",
	subInfoName = "subinfo.txt",
	subBundleName = "subbundles.txt",

	-- 状态变量
	totalNum = 0,      -- 总共要加载的文件数量
	curNum = 0,        -- 当前正在加载的文件
	totalSize = 0,     -- 总大小
	curSize = 0,       -- 已加载大小

	hostUrl = "",
	hostUrlSub = "",
	checkKeys = {},    -- 远程文件列表
	innerKeys = nil,	-- 分包文件列表
	downKeys = {},	-- 需要下载的文件列表
	cusKeys = {},      -- 用户确认下载的列表
	_error = "net_error",
}

AppLoader = P

local use_sub_package = bee.checkVersion("1.7.0") and CS.AppLoader.isEncryptor

----------------------------------------------------------------------
-- 辅助函数：从文件列表文本解析 AddrResInfo 列表
-- 每行格式: "filename,size"
----------------------------------------------------------------------
local function getKeys(text)
	if not text or "" == text then
		return {}
	end
	local keys = {}
	for line in string.gmatch(text, "([^\n]+)") do
		local parts = {}
		for part in string.gmatch(line, "([^,]+)") do
			table.insert(parts, part)
		end
		local info = { file = parts[1] or "", size = tonumber(parts[2]) or 0 }
		table.insert(keys, info)
	end
	return keys
end

local function getKeysList(text)
	local keys = getKeys(text)
	local list = {}
	for _, v in ipairs(keys) do
		table.insert(list, v.file)
	end
	return list
end

-- 检查文件是否以 .bundle 结尾
local function isBundle(file)
	return string.sub(file, -7) == ".bundle"
end

----------------------------------------------------------------------
-- 获取差异文件列表 (keys - fromKeys)
-- keys: AddrResInfo 列表
-- fromKeys: string 列表
-- onlyBundle: 是否只比较 .bundle 文件
----------------------------------------------------------------------
local function getDiffKeys(keys, fromKeys, onlyBundle)
	local diff = {}
	for _, c in ipairs(keys) do
		local fileName = c.file
		if (not onlyBundle) or isBundle(fileName) then
			local found = false
			for _, i in ipairs(fromKeys) do
				if fileName == i then
					found = true
					break
				end
			end
			if not found then
				table.insert(diff, c)
			end
		end
	end
	return diff
end

local function getSameKeys(keys, fromKeys)
	local same = {}
	for _, c in ipairs(keys) do
		local fileName = c.file
		if isBundle(fileName) then
			for _, i in ipairs(fromKeys) do
				if fileName == i then
					table.insert(same, c)
					break
				end
			end
		end
	end
	return same
end

----------------------------------------------------------------------
-- 路径相关
----------------------------------------------------------------------
local function getAddressWritePath()
	return CS.AppLoader.GetAddressWritePath()
end

local function getAddressWriteTempPath()
	return CS.AppLoader.GetAddressWriteTempPath()
end

----------------------------------------------------------------------
-- 单个文件下载
-- url: 远程地址
-- dest: 本地保存路径
-- onProgress: function(progress) 0~1 的下载进度
-- onSuc: function() 下载成功回调
-- onFail: function() 下载失败回调
----------------------------------------------------------------------
local function downloadFile(url, dest, onProgress, onSuc, onFail)
    CS.AppLoader.Instance:DownloadFile(url, dest, onSuc, onFail, onProgress)
end

----------------------------------------------------------------------
-- 批量下载文件
-- path: 本地目录
-- diff: AddrResInfo 列表（需要下载的文件）
-- onProgress: function(progress)
-- onResult: function(isSuccess)
-- urlRoot: 远程根 URL
----------------------------------------------------------------------
local function downloadKeys(path, diff, onProgress, onResult, urlRoot)
	P.curNum = 0
	P.totalNum = #diff
	P.curSize = 0
	P.totalSize = 0
	for _, v in ipairs(diff) do
		P.totalSize = P.totalSize + v.size
	end
	if P.totalSize <= 0 then
		P.totalSize = 1
	end

	local isFail = false
	local index = 1

    if onProgress then
        onProgress(0)
    end
	local function downloadNext()
		if isFail or index > #diff then
			if onResult then
				onResult(not isFail)
			end
			return
		end

		local v = diff[index]
		P.curNum = P.curNum + 1
		local fileFullName = path .. "/" .. v.file
		local url = urlRoot .. "/" .. v.file

		print("[AppLoader] 下载资源:" .. url)

		if CS.FileUtils.Exists(fileFullName) then
			print("[AppLoader] 文件已经存在 " .. fileFullName)
			P.curSize = P.curSize + v.size
			if onProgress then
				onProgress(P.curSize / P.totalSize)
			end
			index = index + 1
			downloadNext()
		else
			downloadFile(url, fileFullName,
				function(progress)
					if onProgress then
						onProgress((P.curSize + v.size * progress) / P.totalSize)
					end
				end,
				function()
					P.curSize = P.curSize + v.size
					if onProgress then
						onProgress(P.curSize / P.totalSize)
					end
					index = index + 1
					downloadNext()
				end,
				function()
					isFail = true
					P._error = "net_error"
					if onResult then
						onResult(false)
					end
				end
			)
		end
	end

	downloadNext()
end

----------------------------------------------------------------------
-- 设置远程主机 URL
----------------------------------------------------------------------
function P:SetHost(url)
	self.hostUrl = url
    CS.AppLoader.SetHost(url)
end

function P:getInitKeys()
    local keys = CS.AppLoader.initKeys
    local list = {}
    for i = 0, keys.Count - 1 do
        table.insert(list, keys[i])
    end
    return list
end

function P:isUseSubPackage()
    return use_sub_package
end

----------------------------------------------------------------------
-- 开始静默下载
-- 后台静默下载资源到临时目录
----------------------------------------------------------------------
function P:DoSlientDownload(url, onComplete, onProgress)
	self.hostUrl = url
	self.totalNum = 0
	self.curNum = 0

	CS.HttpManager.Instance:get(self.hostUrl .. "/" .. self.fileListName .. "?t=" .. os.time(), function(text)
		local keys = getKeys(text)
		self.checkKeys = keys
		self.downKeys = getDiffKeys(keys, self:getInitKeys())
		self:startSlientDownload(onComplete, onProgress)
	end, function()
		print("[AppLoader] DoSlientDownload fail!")
		if onComplete then
			onComplete("net_error")
		end
	end)
end

----------------------------------------------------------------------
-- 静默下载核心逻辑
----------------------------------------------------------------------
function P:startSlientDownload(onComplete, onProgress)
	local keys = self.downKeys
	if not keys or #keys == 0 then
		if onComplete then
			onComplete("none")
		end
		return
	end

	CU.PlayerPrefs.DeleteKey("load_slient_result")

	local path = getAddressWriteTempPath()
	CS.FileUtils.CreateDirectory(path)

	downloadKeys(path, keys, onProgress, function(isSuc)
		if not isSuc or self.curNum < self.totalNum then
			if onComplete then
				onComplete(self._error)
			end
		else
			CU.PlayerPrefs.SetString("load_slient_result", "suc")
			if onComplete then
				onComplete("complete")
			end
		end
	end, self.hostUrl)
end

----------------------------------------------------------------------
-- 应用静默下载好的资源
-- 将临时目录的文件移动到正式目录，更新 catalog
----------------------------------------------------------------------
function P:ExecuteSlient(isInit)
    return CS.AppLoader.ExecuteSlient(isInit)
end

----------------------------------------------------------------------
-- 检查下载热更（用户交互）
-- 先拉取文件列表，与本地对比，如有差异则回调 onTip 通知用户
----------------------------------------------------------------------
function P:DoDownLoad(url, onComplete, onProgress, onTip)
    if not use_sub_package then
        CS.AppLoader.Instance:DoDownLoad(url, onComplete, onProgress, onTip)
        return
    end

	self.hostUrl = url
	self.totalNum = 0
	self.curNum = 0

	CS.HttpManager.Instance:get(self.hostUrl .. "/" .. self.fileListName .. "?t=" .. os.time(), function(text)
        CS.AppLoader.SetCheckKeys(text)
		local keys = getKeys(text)
		self.checkKeys = keys
		self:initPackageKeys()
		local same = getSameKeys(self.innerKeys, self:getInitKeys())
		local diff = getDiffKeys(keys, self:getInitKeys())
		for _, v in ipairs(same) do
			table.insert(diff, v)
		end
		self.downKeys = diff
		if onTip and #diff > 0 then
			local size = 0
			for _, v in ipairs(diff) do
				size = size + v.size
			end
			onTip(size)
		else
			self:startSlientDownload(onComplete, onProgress)
		end
	end, function(err)
		print("[AppLoader] DoDownLoad fail! " .. self.hostUrl .. " " .. tostring(err))
		if onComplete then
			onComplete("filelist_error")
		end
	end)
end

function P:initPackageKeys()
	if not self.innerKeys then
		local inner = CU.Resources.Load("subbundles")
		if inner then
			self.innerKeys = getKeys(inner.text)
		else
			self.innerKeys = {}
		end
	end
end

function P:DoDownloadPackage(url, onComplete, onProgress, onTip)
    if not use_sub_package then
		if onComplete then
			onComplete("none")
		end
        return
    end
	self:initPackageKeys()

	self.hostUrl = url
	self.totalNum = 0
	self.curNum = 0

	if #self.innerKeys > 0 then
		local same = getSameKeys(self.innerKeys, self:getInitKeys())
		self.downKeys = same
		if onTip and #same > 0 then
			local size = 0
			for _, v in ipairs(same) do
				size = size + v.size
			end
			onTip(size)
		else
			self:startSlientDownload(onComplete, onProgress)
		end
	else
		if onComplete then
			onComplete("none")
		end
	end
end

function P:DoDownloadSubPackage(url, idx, onComplete, onProgress)
    CS.AppLoader.Instance:DoDownloadSubPackage(url, idx, onComplete, onProgress)
end

----------------------------------------------------------------------
-- 玩家确认下载热更
----------------------------------------------------------------------
function P:StartDownload(onComplete, onProgress)
    if not use_sub_package then
        CS.AppLoader.Instance:StartDownload(onComplete, onProgress)
        return
    end
	self:startSlientDownload(onComplete, onProgress)
end

----------------------------------------------------------------------
-- 工具方法
----------------------------------------------------------------------
function P:GetAddressWritePath()
	return getAddressWritePath()
end

function P:GetAddressWriteTempPath()
	return getAddressWriteTempPath()
end

-- 返回当前进度信息
function P:GetProgress()
	return {
		totalNum = self.totalNum,
		curNum = self.curNum,
		totalSize = self.totalSize,
		curSize = self.curSize,
	}
end

print("[AppLoader] AppLoader.lua loaded")
return P
