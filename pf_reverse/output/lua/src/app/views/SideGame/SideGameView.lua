local P = class("SideGameView", UiBlurBase)

local SubView = {
	[1] = {game_type = GAME_GAME_TYPE.SIDE_GAME_COLOR_GAME, view = "views/ColorGame/ColorGame"},
	[2] = {game_type = GAME_GAME_TYPE.SIDE_GAME_PINBALL_GAME, view = "views/SideGame/Pinball"},
}

function P:onAwake()
	self._openAnim, self._closeAnim = "UI_1_SideGameView_into", "UI_1_SideGameView_back"
	local AnimRoot = self:find("AnimRoot")
	self.Center = self:find("Center", AnimRoot)
	local TabToggle = self:find("Left/Tab/TabToggle", AnimRoot)
	self._toggleList = {}
	for i = 1, 2 do
		table.insert(self._toggleList, self:find("Tab0" .. i, TabToggle))
		bee.addClick(self._toggleList[i], function()
			if self._selectedType == SubView[i].game_type then
				return
			end
			Game:playSound("ui_tab_switch_1")
			self._selectedType = SubView[i].game_type
			self:refreshTab()
			self:refreshCenter()
		end)
	end

	bee.addClick(self:find("Mask"), function ()
		self:hideUI()
	end)
end

function P:onStart()
	if self._params and self._params.jump then
		self._selectedType = self._params.jump.select
	else
		self._selectedType = SideGameModel:getLastSideGameType()
	end

	self:refreshTab()
	self:refreshCenter()
end

function P:onDestroy()
	SideGameModel:setLastSideGameType(self._selectedType)
end

function P:preHide()
    P.super.preHide(self)
	bee.emit("evt_sideGameViewHide")
end

function P:refreshTab()
	for k, v in pairs(self._toggleList) do
		self:find("On", v):SetActive(SubView[k].game_type == self._selectedType)
		self:find("Off", v):SetActive(SubView[k].game_type ~= self._selectedType)
	end
end

function P:refreshCenter()
	local viewInfo
	for k,v in pairs(SubView) do
		if v.game_type == self._selectedType then
			viewInfo = v
			break
		end
	end
	if not viewInfo then
		return
	end

	if viewInfo.game_type == GAME_GAME_TYPE.SIDE_GAME_PINBALL_GAME then
		SideGameModel:setShowPinball()
        bee.logEvent("pinball-lobby")
	elseif viewInfo.game_type == GAME_GAME_TYPE.SIDE_GAME_COLOR_GAME then
        bee.logEvent("colorgame-lobby")
	end

	if self._curSubView then
		CU.GameObject.Destroy(self._curSubView)
		self._curSubView = nil
	end

	self._curSubView = bee.createObj(viewInfo.view)
	self._curSubView.transform:SetParent(self.Center.transform)
	local rectTrans = self._curSubView.transform:GetComponent("RectTransform")
	rectTrans.offsetMin = bee.v2(0, 0)
	rectTrans.offsetMax = bee.v2(0, 0)
	self._curSubView.transform.localScale = bee.v3(1, 1, 1)
	self._curSubViewCls = ObjectPool:getCls(self._curSubView)
end

function P:evt_hideSideGame()
	self:hideUI()
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction")
end

function P:evt_uiBlur(flag, name)
    self:onUiBlur(flag, name)
end

function P:evt_gameBlur(flag, name)
    self:onUiBlur(flag, name)
end

