local P = {
	Version = "1.6.4",

    --标识
    escCtrlSign = true,

    --弹窗类
    topViewList = {
		"CommonItemTip",
		"CommonIconTextTipUD",
		"CommonItemTipLR",
		"CommonNotice",
		"CommonNoticeSmall",
		"CommonNoticeSmall2",
		"CommonPackageTip",
		"CommonTextTipBigRL",
		"CommonTextTipRL",
		"CommonTextTipUD",
	},

	--不可操作界面
	cantCtrlList = {
		"LoadingLayer", --Loading
		"GachaWheelMask", --招募
		"GachaResultShow", --招募
		"Story", --剧情
		"TournamentPrizePoolDraw", --奖池
		"IngameBankrupt", --破产推送
		"UpdateVersion", --更新提示
	},
}
ShortcutKeyManager = P

--ESC键
function P:InputEscape()
	if not bee.checkVersion("1.6.4") then
		return
	end

	--引导过程无效
	if GuideManager:isInGuide() then
		return
	end
	--标识异常无效
	if not self.escCtrlSign then
		return
	end

	--Top层界面
	for _,v in pairs(self.topViewList) do
		local _uiView = UiManager:getUI(v)
		if _uiView and _uiView.transform.parent == UiManager:getPopRoot().transform then
			_uiView:onBtClose()
			return
		end
	end

	local uiName = self:getTopestViewName()

	--登录界面
	if uiName == "LoginStartLayer" or uiName == "LoginLayer" then
		UiManager:showTip({
            text = _T("LAB_SETTINGS_108"),
            onSure = function()
                Game:quit()
            end
        })
		return
	end
	local uiView = UiManager:getUI(uiName)

	--如果是大厅
	if bee.isInHome() and uiName == "LobbyLayer" then
        if uiView and uiView:getUIVisibleSign() then
            return
        end
		UiManager:showTip({
            text = _T("LAB_SETTINGS_108"),
            onSure = function()
                Game:quit()
            end
        })
		return
	end

	--如果是局内
	if bee.isInGame() then
		if uiName == "PKActionLayer" or uiName == "PKActionAllinLayer" or uiName == "TournamentSNGUILayer" then
			bee.emit("evt_shortcutOpenMenu")
			return
		elseif uiName == "PKMenu" then
			bee.emit("evt_shortcutExitTable")
			return
		end

		--围观
		if GameModel.data:isInObserve() then
            if uiName == "IngameSpectate" or uiName == "FriendsRoomOutlook" then
                bee.emit("evt_shortcutOpenMenu")
                return
            end
		end
	end

	--不可操作界面
	if table.keyof(self.cantCtrlList, uiName) ~= nil then
		return
	end

	--弹窗界面
	for _,v in pairs(self.topViewList) do
		local _uiView = UiManager:getUI(v)
		if _uiView then
			_uiView:onBtClose()
			return
		end
	end

	--普通界面
    if uiView then
	    uiView:onBtClose()
    end
end

--获取最顶层界面
function P:getTopestViewName()
	local layer = -1
	local uiName = ""
    local uiStack = UiManager:getUiStack()
	for k,v in pairs(uiStack) do
		local canvas = v.node:GetComponent("Canvas")
		if not bee.isNull(canvas) and canvas.sortingOrder > layer and v.node.transform.parent.gameObject == UiManager:getUiRoot() then
			layer = canvas.sortingOrder
			uiName = v.cls.uiName
		end
	end
	return uiName
end


--特殊过程标识
function P:switchEscCtrlSign(val)
	self.escCtrlSign = val
end


return P