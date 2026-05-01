local P = class("BackpackLobbyPreview", UiDialog)

function P:onAwake()
	self.AnimRoot = self:find("AnimRoot")

	self.LobbyImg = self:find("Center/LobbyImg", self.AnimRoot)
	self.PageRightButton = self:find("Right/PageRightButton", self.AnimRoot)
	self.PageLeftButton = self:find("Left/PageLeftButton", self.AnimRoot)
	self.TextName = self:find("LeftBottom/SceneTitle/TextName", self.AnimRoot)
	self.BackButton = self:find("LeftTop/BackButton", self.AnimRoot)

	bee.addClick(self.BackButton, function()
		self:onClickClose()
	end)
	bee.addClick(self.PageLeftButton, function()
		self:onClickLeft()
	end)
	bee.addClick(self.PageRightButton, function()
		self:onClickRight()
	end)
end

function P:onStart()
	self._itemDatas = self._params.list
	self._count = #self._itemDatas
	self._index = 1
	for i,v in ipairs(self._itemDatas) do
		if self._params.data.item_id == v.item_id then
			self._index = i
			break
		end
	end
	
	self:refreshButton()
end

function P:setSceneShow()
	local data = self._itemDatas[self._index]
	local propCfg = tpl_props[data.item_id or data.id]
	local sceneCfg = tpl_hall_scene[propCfg.mapId]

	bee.setIcon(self.LobbyImg, sceneCfg.bg_image)
	bee.setText(self.TextName, _T(propCfg.name))
end

function P:onClickLeft()
	self._index = self._index - 1
	self:refreshButton()
end

function P:onClickRight()
	self._index = self._index + 1
	self:refreshButton()
end

function P:refreshButton()
	if #self._itemDatas <= 1 then
		self.PageLeftButton:SetActive(false)
		self.PageRightButton:SetActive(false)
	elseif self._index <= 1 then
		self._index = 1
		self.PageLeftButton:SetActive(false)
		self.PageRightButton:SetActive(true)
	elseif self._index >= self._count then
		self._index = self._count
		self.PageLeftButton:SetActive(true)
		self.PageRightButton:SetActive(false)
	else
		self.PageLeftButton:SetActive(true)
		self.PageRightButton:SetActive(true)
	end

	self:setSceneShow()
end

function P:onClickClose()
	if self._params.cb then
		self._params.cb(self._itemDatas[self._index])
	end
	self:hideUI()
end

return P