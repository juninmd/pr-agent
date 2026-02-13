from __future__ import annotations

from pr_agent.config_loader import get_settings
from pr_agent.log import get_logger


def ticket_markdown_logic(emoji, markdown_text, value, gfm_supported) -> str:
    ticket_compliance_str = ""
    compliance_emoji = ''
    # Track compliance levels across all tickets
    all_compliance_levels = []

    if isinstance(value, list):
        for ticket_analysis in value:
            try:
                ticket_url = ticket_analysis.get('ticket_url', '').strip()
                explanation = ''
                ticket_compliance_level = ''  # Individual ticket compliance
                fully_compliant_str = ticket_analysis.get('fully_compliant_requirements', '').strip()
                not_compliant_str = ticket_analysis.get('not_compliant_requirements', '').strip()
                requires_further_human_verification = ticket_analysis.get('requires_further_human_verification',
                                                                          '').strip()

                if not fully_compliant_str and not not_compliant_str:
                    get_logger().debug(f"Ticket compliance has no requirements",
                                       artifact={'ticket_url': ticket_url})
                    continue

                # Calculate individual ticket compliance level
                if fully_compliant_str:
                    if not_compliant_str:
                        ticket_compliance_level = 'Partially compliant'
                    else:
                        if not requires_further_human_verification:
                            ticket_compliance_level = 'Fully compliant'
                        else:
                            ticket_compliance_level = 'PR Code Verified'
                elif not_compliant_str:
                    ticket_compliance_level = 'Not compliant'

                # Store the compliance level for aggregation
                if ticket_compliance_level:
                    all_compliance_levels.append(ticket_compliance_level)

                # build compliance string
                if fully_compliant_str:
                    explanation += f"Compliant requirements:\n\n{fully_compliant_str}\n\n"
                if not_compliant_str:
                    explanation += f"Non-compliant requirements:\n\n{not_compliant_str}\n\n"
                if requires_further_human_verification:
                    explanation += f"Requires further human verification:\n\n{requires_further_human_verification}\n\n"
                ticket_compliance_str += f"\n\n**[{ticket_url.split('/')[-1]}]({ticket_url}) - {ticket_compliance_level}**\n\n{explanation}\n\n"

                # for debugging
                if requires_further_human_verification:
                    get_logger().debug(f"Ticket compliance requires further human verification",
                                       artifact={'ticket_url': ticket_url,
                                                 'requires_further_human_verification': requires_further_human_verification,
                                                 'compliance_level': ticket_compliance_level})

            except Exception as e:
                get_logger().exception(f"Failed to process ticket compliance: {e}")
                continue

        # Calculate overall compliance level and emoji
        if all_compliance_levels:
            if all(level == 'Fully compliant' for level in all_compliance_levels):
                compliance_level = 'Fully compliant'
                compliance_emoji = '✅'
            elif all(level == 'PR Code Verified' for level in all_compliance_levels):
                compliance_level = 'PR Code Verified'
                compliance_emoji = '✅'
            elif any(level == 'Not compliant' for level in all_compliance_levels):
                # If there's a mix of compliant and non-compliant tickets
                if any(level in ['Fully compliant', 'PR Code Verified'] for level in all_compliance_levels):
                    compliance_level = 'Partially compliant'
                    compliance_emoji = '🔶'
                else:
                    compliance_level = 'Not compliant'
                    compliance_emoji = '❌'
            elif any(level == 'Partially compliant' for level in all_compliance_levels):
                compliance_level = 'Partially compliant'
                compliance_emoji = '🔶'
            else:
                compliance_level = 'PR Code Verified'
                compliance_emoji = '✅'

            # Set extra statistics outside the ticket loop
            get_settings().set('config.extra_statistics', {'compliance_level': compliance_level})

        # editing table row for ticket compliance analysis
        if gfm_supported:
            markdown_text += f"<tr><td>\n\n"
            markdown_text += f"**{emoji} Ticket compliance analysis {compliance_emoji}**\n\n"
            markdown_text += ticket_compliance_str
            markdown_text += f"</td></tr>\n"
        else:
            markdown_text += f"### {emoji} Ticket compliance analysis {compliance_emoji}\n\n"
            markdown_text += ticket_compliance_str + "\n\n"

    return markdown_text
