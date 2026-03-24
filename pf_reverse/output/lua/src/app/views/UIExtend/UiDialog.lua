-- 对话框 ui 基类
local P = class("UiDialog", UiBlurBase)
UiDialog = P

function P:preShow()
	P.super.preShow(self)

    if not self._stopMaskClick then
        bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
            self:onBtClose()
        end, true)
    end

	bee.emit(EventDef.evt_uiBlur, true, self.__cname)
end

function P:preHide()
	bee.emit(EventDef.evt_uiBlur, false, self.__cname)
	return P.super.preHide(self)
end

function P:evt_uiBlur(flag, name)
    self:onUiBlur(flag, name)
end

function P:evt_gameBlur(flag, name)
    self:onUiBlur(flag, name)
end

function P:onBtClose()
    self:hideUI()
end

