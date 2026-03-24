require "app.GMContent"

local P = class("GMDialog", UiBase)


function P:onAwake()
	P.super.onAwake(self)
	self.inPop = true
	self.Dialog = self:find("PopDialog/Dialog")
	self.CommonList = self:find("CommonList", self.Dialog)
	self.Item = self:find("Item", self.CommonList)
	self.Item:SetActive(false)

	self._InputComment = self:find("InputComment", self.Dialog)
	self._BtCommit =self:find("BtCommit", self.Dialog)
    self._GMDropdown=self:find("GMDropdown", self.Dialog)
	
	bee.setText(self._InputComment,self._lastCode,"InputField")
	bee.addClick(self._BtCommit,function ()
		self:onBtCommon()
	end)
	bee.addClick(self:find("BtClose", self.Dialog),function ()
		self:hideUI()
	end)
end

function P:onStart()
	self._gms = LocalStore:getTableData("gm_cmd_history") or {}

	self._cmdList = UiListEx:create(self.CommonList)
	self._cmdList:setWidth(90)
	self._cmdList:setCreateFunc(function(data)
		return CU.GameObject.Instantiate(self.Item)
	end)
	self._cmdList:setRefreshFunc(function(data, item)
		bee.setText(self:find("Text", item), data.examples .. " " .. data.notes)
		self:find("BgSel", item):SetActive(nil ~= data.selected)
		bee.addClick(item, function()
			for _, v in ipairs(GMContent) do
				if v.selected then
					v.selected = nil
					local n = self._cmdList:getDataNode(v)
					if not bee.isNull(n) then
						self:find("BgSel", n):SetActive(false)
					end
				end
			end
			data.selected = true
			self:find("BgSel", item):SetActive(true)
			bee.setText(self._InputComment, self:getGmStr(data.examples), "InputField")
		end, true)
	end)

	local code = LocalStore:getStringForKey("gm_last_code")
	if code and code ~= "" then
		bee.setText(self._InputComment, code, "InputField")
		local strls=string.split(code," ")
		if #strls > 0 then
			local cmd = strls[1]
			for _, v in ipairs(GMContent) do
				strls = string.split(v.examples, " ")
				if cmd == strls[1] then
					v.selected = true
					break
				end
			end
		end
	else
		bee.setText(self._InputComment, self:getGmStr(GMContent[1].examples), "InputField")
		GMContent[1].selected = true
	end

	self._cmdList:setDatas(GMContent)
end

function P:getGmStr(cmd)
	local s = string.split(cmd, " ")
	if self._gms[s[1]] then
		return self._gms[s[1]]
	end
	return cmd
end

function P:onBtCommon()
	local inputCode=bee.getText(self._InputComment,"InputField")
    if not string.find(inputCode,"#") then
		UiManager:showToast(_T("请输入#加命令 加空格 加参数的格式"), bee.v3(0, 0));
		return 
	end
	local strls=string.split(inputCode," ")
	--print(strls[1],strls[2])
	UiManager:showToast(_T("执行命命令"..strls[1]), bee.v3(0, 0))
	if self:EimtFunc(strls[1],strls[2],strls[3]) then
		LocalStore:setStringForKey("gm_last_code", inputCode)
		self._gms[strls[1]] = inputCode
		LocalStore:saveTableData("gm_cmd_history", self._gms)
	end
	self:hideUI()
end

function P:EimtFunc(funName,...)
	local args, i = {...}, 1
	for _, v in pairs(GMContent) do
		if string.find(v.examples, funName) and v.cb then
			return v.cb(args) ~= false
		end
	end
	return true
end

return P
