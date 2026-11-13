export interface ChatMessage {
  id: string;
  sender: 'bot' | 'user' | 'system';
  text: string;
  timestamp: number;
  message_type: 'text' | 'question' | 'otp_alert' | 'captcha_alert' | 'success_alert' | 'link_card' | 'error' | 'fill_prompt' | 'otp_prompt' | 'otp_validate_prompt';
  field_id?: string;
  options?: string[];
  metadata?: Record<string, any>;
}

export interface BrowserStatus {
  is_connected: boolean;
  current_url: string;
  automation_status: 'idle' | 'connecting' | 'navigating' | 'website_opened' | 'inspecting' | 'page_inspected' | 'analyzing' | 'fields_identified' | 'awaiting_user_input' | 'awaiting_confirmation' | 'filling_form' | 'verifying_fields' | 'awaiting_submission' | 'submitting' | 'awaiting_otp' | 'awaiting_captcha' | 'verified' | 'error';
  last_inspection_summary: string;
  detected_step: string;
  last_updated: number;
}

