local P = class("SevenDayTaskplot", UiDialog)

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", AnimRoot)

	local PlotScrollViewCont = self:find("PlotScrollView/Viewport/Content", Center)
	self.ContentText = self:find("ContentText", PlotScrollViewCont)
	self.TimeText = self:find("TimeText", PlotScrollViewCont)
	self.CloseButton = self:find("CloseButton", Center)

	bee.addClick(self.CloseButton, function()
		if self._params.closeCb then
			self._params.closeCb()
		end
		self:hideUI()
	end)
	bee.addClick2(self:find("common_panel_mask_80", Center), function()
		if self._params.closeCb then
			self._params.closeCb()
		end
		self:hideUI()
	end)

	Game:playSound("ui_7daytask_plot_show")
end

function P:onStart()
	local stageCfg = tpl_seven_day_tasks_stage[self._params.id]
	bee.setText(self.ContentText, _T(stageCfg.plot_text))
	bee.setText(self.TimeText, _T(stageCfg.plot_time))
end

