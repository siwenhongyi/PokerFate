-- 全屏 ui 基类
local P = class("UiFullView", UiBlurBase)
UiFullView = P

function P:ctor(params)
    P.super.ctor(self, params)
	self._openAnim, self._closeAnim = "UI_1_" .. self.__cname .. "_into", "UI_1_" .. self.__cname .. "_back"
end

function P:preShow()
	P.super.preShow(self)
	bee.emit(EventDef.evt_backgroundBlur, true, self.__cname)
	bee.emit(EventDef.evt_uiBlur, true, self.__cname)
end

function P:preHide()
	bee.emit(EventDef.evt_backgroundBlur, false, self.__cname)
	bee.emit(EventDef.evt_uiBlur, false, self.__cname)
	local n = CU.GameObject("HideMask")
	local cmp = n:AddComponent(typeof(CU.UI.Image))
	cmp.color = CU.Color(1, 1, 1, 0)
	n.transform:SetParent(self.node.transform, false)
	n.transform.sizeDelta = bee.v2(SCREEN_WIDTH, SCREEN_HEIGHT)
	return P.super.preHide(self)
end

function P:playToggleInto(AnimRoot)
	AnimRoot:GetComponent("Animator"):Play("UI_1_BackpackMain_ToggleScrollView_into")
end

function P:playToggleIdle2(AnimRoot)
	AnimRoot:GetComponent("Animator"):Play("UI_1_BackpackMain_ToggleScrollView_idle2")
end

function P:evt_uiBlur(flag, name)
    self:onUiBlur(flag, name)
end

function P:evt_gameBlur(flag, name)
    self:onUiBlur(flag, name)
end

