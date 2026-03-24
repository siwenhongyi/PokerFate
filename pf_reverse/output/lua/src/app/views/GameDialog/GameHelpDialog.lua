local P = class("GameHelpDialog", UiDialogWindowWM)

function P:onAwake()
	P.super.onAwake(self)
	self._BtPre=self:find("PanelBg/BtPre",self._windDialog)
	self._BtNext=self:find("PanelBg/BtNext",self._windDialog)
	self._List = self:find("PanelBg/Scroll View",self._windDialog)
	self._Content = self:find("Viewport/Content", self._List)

	self._startIndex = 1

	self._PageView = self._List:GetComponent(typeof(CS.PageView))
	self._PageView:OnPageChange(function()
		self:refreshUI()
	end)
end

function P:onStart()
	if self._params and self._params.startIndex then
		self._startIndex = self._params.startIndex
		for i = 1, self._params.startIndex - 1 do
			local obj = self:find(string.format("GameHelp%02d", i), self._Content)
			if obj then
				-- obj:SetActive(false)
				CU.GameObject.Destroy(obj)
			end
		end
		self._PageView.enabled = false;
		self:once(0.1, function() self._PageView.enabled = true end)
	end
	P.super.onStart(self)
	bee.AddClick(self._BtPre,function ()
		local index = self._PageView:GetCurIndex()
		if index > 0 then
			self._PageView:PageTo(index - 1)
			self:refreshUI()
		end
	end)
	bee.AddClick(self._BtNext,function ()
		local index = self._PageView:GetCurIndex()
		if index < self._PageView:GetPageCount() - 1 then
			self._PageView:PageTo(index + 1)
			self:refreshUI()
		end
	end)
	self._BtPre:SetActive(false)
	self._BtNext:SetActive(true)
    bee.logEvent("enter_help")

	self._helps = {}

	self:loadHelp(1)
	scheduler:once(0.1, function()
		self:loadHelp(2)
	end)
end

function P:refreshUI()
	local index = self._PageView:GetCurIndex()
	local mIndex = self._PageView:GetPageCount()
	self._BtPre:SetActive(index > 0)
	self._BtNext:SetActive(index < self._PageView:GetPageCount() - 1)
	self:loadHelp(index + 1)
	if index < mIndex then
		self:loadHelp(index + 2)
	end
end

function P:loadHelp(index)
	index = index + self._startIndex - 1
	if index >= 1 and index <= 6 then
		if not self._helps[index] then
			local i = string.format("GameHelp%02d", index)
			local obj = bee.createObj("views/GameHelp/" .. i)
			obj.transform:SetParent(self:find(i, self._Content).transform, false)
			self._helps[index] = obj
		end
	end
end

return P
